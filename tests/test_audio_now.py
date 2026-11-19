"""Sound right after installing audio support, without logging out and in.

PipeWire was started only at login (session-audio start, from abyss-session
and ~/.xinitrc). Installing the "Audio support" bundle in a running session
left it off until the next login: no sound, no volume in the bar, and the
Super+Alt+A mixer said "Connection to PulseAudio failed". Covers:
  * session-audio now starts PipeWire for the caller's graphical session,
    detached from the install terminal (setsid), refreshes the bar, and
    `stop` at logout ends those processes like the ones started at login;
    it does nothing for root, without DISPLAY or without the runtime
    directory, and keeps a PipeWire this session already runs;
  * abyss-software --run-install runs it, as the user, after installing
    pipewire, wireplumber or pipewire-pulse (not for other packages, a
    refused password, or when the install itself runs as root);
  * the `install` shell helper does the same;
  * dwm-statusbar shows the volume block within a tick once wpctl appears,
    instead of re-checking only once a minute.
Every command that would start, signal or look up a real process (id, pgrep,
pkill, setsid, the PipeWire programs, abyss-bar, xbps, doas) is a stub first
in PATH; /proc is a fake tree.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

from test_session_audio import AUDIO, BUS, NAMES, PGREP, PKILL, START, UID
import test_software_packages as software
import test_statusbar as statusbar

# the shell helpers of the same abyss-desktop as session-audio
PROFILE = os.environ.get('ABYSS_PROFILE') or (
    str(AUDIO.parent / 'zz-abyss-cli.sh') if (AUDIO.parent / 'zz-abyss-cli.sh').is_file() else software.PROFILE)


@unittest.skipUnless(AUDIO.is_file(), 'session-audio not found; set ABYSS_DESKTOP_PKG')
class SessionAudioNowTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='san')
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name).resolve()
        self.bin = self.dir / 'bin'
        self.rt = self.dir / 'rt'
        for d in (self.bin, self.rt, self.dir / 'state', self.dir / 'proc'):
            d.mkdir(mode=0o700)
        # a normal user unless FAKE_ID says otherwise (CI runs as root)
        self.stub('id', f'#!/bin/sh\necho "${{FAKE_ID:-{UID}}}"\n')
        self.stub('pgrep', PGREP)
        self.stub('pkill', PKILL)
        for name in NAMES:
            self.stub(name, START)
        self.stub('setsid', '#!/bin/sh\nprintf \'%s\\n\' "setsid $*" >> "$FAKE/log"\n'
                            '[ "$1" = -w ] && shift\nexec "$@"\n')
        self.stub('abyss-bar', '#!/bin/sh\nprintf \'%s\\n\' "abyss-bar $*" >> "$FAKE/log"\n')

    def stub(self, name, text):
        p = self.bin / name
        p.write_text(text)
        p.chmod(0o755)

    def env(self, **extra):
        env = {'PATH': f'{self.bin}:/usr/bin:/bin:/usr/sbin:/sbin', 'HOME': str(self.dir), 'LC_ALL': 'C',
               'FAKE': str(self.dir), 'ABYSS_PROC_DIR': str(self.dir / 'proc'), 'DISPLAY': ':0',
               'XDG_RUNTIME_DIR': str(self.rt), 'DBUS_SESSION_BUS_ADDRESS': BUS}
        env.update(extra)
        return {k: v for k, v in env.items() if v is not None}

    def run_audio(self, *args, **env):
        r = subprocess.run(['/bin/sh', str(AUDIO), *args], env=self.env(**env), stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout)
        return r.stdout

    def log(self):
        p = self.dir / 'log'
        lines = p.read_text().splitlines() if p.exists() else []
        p.unlink(missing_ok=True)
        return lines

    def running(self, name):
        p = self.dir / 'state' / name
        return p.read_text().split() if p.exists() else []

    def test_now_starts_for_this_session_and_logout_stops_it(self):
        out = self.run_audio('now')
        self.assertIn('Sound is on for this session', out)
        calls = self.log()
        self.assertEqual(calls[0], f'setsid -w /bin/sh {AUDIO} start')
        self.assertEqual(calls[1], 'pipewire ')
        self.assertEqual(sorted(calls[2:4]), ['pipewire-pulse ', 'wireplumber '])
        self.assertEqual(calls[4:], ['abyss-bar --refresh'])        # the bar shows the volume now
        for name in NAMES:
            pids = self.running(name)
            self.assertEqual(len(pids), 1, name)
            environ = (self.dir / 'proc' / pids[0] / 'environ').read_bytes().split(b'\0')
            # what `stop` (abyss-session at logout) checks to call them its own
            self.assertIn(f'XDG_RUNTIME_DIR={self.rt}'.encode(), environ)
            self.assertIn(f'DBUS_SESSION_BUS_ADDRESS={BUS}'.encode(), environ)
        # logout: abyss-session's `stop` ends them
        self.run_audio('stop', DISPLAY=None)
        self.assertEqual(self.log(), [f'pkill -u {UID} -x {n}' for n in NAMES])
        self.assertEqual([self.running(n) for n in NAMES], [[], [], []])

    def test_now_keeps_pipewire_this_session_runs(self):
        self.run_audio('start')
        self.log()
        before = {n: self.running(n) for n in NAMES}
        self.run_audio('now')
        self.assertEqual(self.log(), [f'setsid -w /bin/sh {AUDIO} start', 'abyss-bar --refresh'])
        self.assertEqual({n: self.running(n) for n in NAMES}, before)

    def test_now_needs_a_users_graphical_session(self):
        missing = self.dir / 'gone'
        for case, env in (('root', {'FAKE_ID': '0'}),
                          ('no DISPLAY', {'DISPLAY': None}),
                          ('empty DISPLAY', {'DISPLAY': ''}),
                          ('no runtime directory', {'XDG_RUNTIME_DIR': None}),
                          ('runtime directory missing', {'XDG_RUNTIME_DIR': str(missing)})):
            with self.subTest(case):
                self.assertEqual(self.run_audio('now', **env), '')
                self.assertEqual(self.log(), [])
                self.assertEqual([self.running(n) for n in NAMES], [[], [], []])
                self.assertFalse(missing.exists())
                self.assertFalse(Path(f'/tmp/runtime-{UID}-unused').exists())

    def test_now_without_pipewire_installed_does_nothing(self):
        system = '/usr/bin:/bin:/usr/sbin:/sbin'
        if shutil.which('pipewire', path=system):
            self.skipTest('pipewire is installed on this system')
        for name in NAMES:
            (self.bin / name).unlink()
        self.assertEqual(self.run_audio('now', PATH=f'{self.bin}:{system}'), '')
        self.assertEqual(self.log(), [])


AUDIO_LOG_STUB = 'printf \'%s DISPLAY=%s\\n\' "$*" "${DISPLAY:-}" >> "$HOME/audio.log"'


class SoftwareInstallTest(software.StubbedTest):
    """abyss-software --run-install, as the user in the install terminal."""

    def setUp(self):
        super().setUp()
        audio = self.root / 'session-audio'
        audio.write_text('#!/bin/sh\n' + AUDIO_LOG_STUB + '\n')
        audio.chmod(0o755)
        self.env.update({'ABYSS_SESSION_AUDIO': str(audio), 'DISPLAY': ':0'})
        # the user; abyss-priv runs the command as (fake) root
        self.stub('abyss-priv', 'FAKE_ROOT=1 exec "$@"')
        self.stub('doas', 'FAKE_ROOT=1 exec "$@"')
        self.stub('id', '[ "$1" = -u ] && [ -n "$FAKE_ROOT" ] && { echo 0; exit; }; echo 1000')

    def test_audio_bundle_starts_pipewire_for_the_session(self):
        out = self.software('--run-install', '--yes', 'pipewire', 'wireplumber', 'pavucontrol')
        self.assertEqual(self.status, 0, out)
        self.assertIn('-y pipewire wireplumber pavucontrol', self.installs())
        self.assertEqual(self.log('audio.log'), ['now DISPLAY=:0'])   # once, as the user

    def test_each_pipewire_package_counts(self):
        for pkg in ('wireplumber', 'pipewire-pulse'):
            with self.subTest(pkg):
                (self.root / 'audio.log').unlink(missing_ok=True)
                self.software('--run-install', '--yes', pkg)
                self.assertEqual(self.log('audio.log'), ['now DISPLAY=:0'])

    def test_other_packages_leave_audio_alone(self):
        out = self.software('--run-install', '--yes', 'vlc', 'pavucontrol')
        self.assertEqual(self.status, 0, out)
        self.assertEqual(self.log('audio.log'), [])

    def test_refused_password_starts_nothing(self):
        for tool in ('abyss-priv', 'doas'):
            self.stub(tool, 'echo "doas: Authentication failed" >&2; exit 1')
        self.software('--run-install', '--yes', 'pipewire')
        self.assertNotEqual(self.status, 0)
        self.assertEqual(self.log('audio.log'), [])

    def test_install_run_as_root_does_not_start_roots_audio(self):
        self.stub('id', '[ "$1" = -u ] && { echo 0; exit; }; echo 0')
        out = self.software('--run-install', '--yes', 'pipewire', 'wireplumber')
        self.assertEqual(self.status, 0, out)
        self.assertEqual(self.log('audio.log'), [])


@unittest.skipUnless(PROFILE and Path(PROFILE).is_file(), 'zz-abyss-cli.sh not found; set ABYSS_PROFILE')
class ShellInstallTest(SoftwareInstallTest):
    """The `install` helper of /etc/profile.d/zz-abyss-cli.sh."""

    def shell(self, code):
        result = subprocess.run(['bash', '--norc', '--noprofile', '-i', '-c', f'. "{PROFILE}"; {code}'],
                                env={**self.env, 'PS1': '$ '}, cwd=self.root, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, timeout=60)
        self.status, self.output = result.returncode, result.stdout
        return result.stdout

    def test_audio_bundle_starts_pipewire_for_the_session(self):
        out = self.shell('install pipewire wireplumber pavucontrol')
        self.assertEqual(self.status, 0, out)
        self.assertIn('pipewire wireplumber pavucontrol', self.log('xbps.log'))
        self.assertEqual(self.log('audio.log'), ['now DISPLAY=:0'])

    def test_each_pipewire_package_counts(self):
        for pkg in ('wireplumber', 'pipewire-pulse'):
            with self.subTest(pkg):
                (self.root / 'audio.log').unlink(missing_ok=True)
                self.shell(f'install {pkg}')
                self.assertEqual(self.log('audio.log'), ['now DISPLAY=:0'])

    def test_other_packages_leave_audio_alone(self):
        self.shell('install vlc; install -m 644 a/pipewire b/pipewire')
        self.assertEqual(self.log('audio.log'), [])

    def test_refused_password_starts_nothing(self):
        for tool in ('abyss-priv', 'doas', 'sudo'):
            self.stub(tool, 'echo "doas: Authentication failed" >&2; exit 1')
        self.shell('install pipewire')
        self.assertNotEqual(self.status, 0)
        self.assertEqual(self.log('audio.log'), [])

    def test_install_run_as_root_does_not_start_roots_audio(self):
        self.stub('id', '[ "$1" = -u ] && { echo 0; exit; }; echo uid=0')
        self.shell('install pipewire wireplumber')
        self.assertEqual(self.log('audio.log'), [])


@unittest.skipUnless(statusbar.BASH5, 'dwm-statusbar needs bash 5')
class StatusbarVolumeAppearsTest(unittest.TestCase):
    def test_volume_shows_within_a_tick_once_wpctl_is_installed(self):
        box = statusbar.Sandbox()
        self.addCleanup(box.close)
        wpctl = (box.bin / 'wpctl').read_text()
        (box.bin / 'wpctl').unlink()                       # no audio support yet
        box.file('volume', 'Volume: 0.42\n')
        box.file('config/abyss/bar.conf', 'INTERVAL=0.1\n')
        statusbar.stub(box.bin, 'xsetroot', '[ "$1" = -name ] && printf "%s\\0" "$2" >> "$HOME/names"')
        for name in ('xrandr', 'abyss-display'):
            statusbar.stub(box.bin, name, 'exit 0')
        p = subprocess.Popen([statusbar.BASH5, str(statusbar.STATUSBAR)], env=box.env(),
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(lambda: (p.poll() is None and p.kill(), p.wait()))
        names = box.home / 'names'

        def wait_for(pred, secs):
            # status lines, NUL-terminated (a block marker may be a newline)
            end = time.time() + secs
            while time.time() < end:
                lines = names.read_text().split('\0')[:-1] if names.exists() else []
                if pred(lines):
                    return lines
                time.sleep(0.05)
            return None

        first = wait_for(lambda lines: lines, 10)
        self.assertTrue(first, 'no status line')
        self.assertNotIn('42%', first[-1])
        time.sleep(0.5)                                    # a few ticks into the minute
        (box.bin / 'wpctl').write_text(wpctl)
        (box.bin / 'wpctl').chmod(0o755)
        # the once-a-minute probe (30 ticks, 3 s here) would be too late
        lines = wait_for(lambda lines: any('42%' in line for line in lines), 1.5)
        self.assertTrue(lines, 'the volume block did not appear within a tick')
        self.assertIn('42%', statusbar.blocks(lines[-1]).get(5, ''))


if __name__ == '__main__':
    unittest.main()
