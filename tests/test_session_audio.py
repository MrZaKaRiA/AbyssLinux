"""PipeWire for each desktop session (abyss-desktop's session-audio).

After logging out of dwm and in again the bar had no volume and `wpctl
status` could not connect: the previous session's pipewire (and
pipewire-pulse) outlived the logout, ~/.xinitrc saw it with pgrep and started
none, but it served the old session (elogind had removed /run/user/UID and
its socket) and wireplumber, which quits with its session bus, was gone.
Covers, with stand-ins for id, pgrep, pkill and the PipeWire programs and a
fake /proc (no real process is looked up, signalled or started):
  * start runs pipewire, then wireplumber and pipewire-pulse once its socket
    exists, and does nothing when this session runs all of them already;
  * it replaces processes of another session (other session bus or runtime
    directory), a pipewire without its socket and a set missing wireplumber,
    with pkill -u <uid> -x <name> (SIGKILL for one that does not quit);
  * stop ends them only when this session started them;
  * without audio support installed it does nothing.
"""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PKG = os.environ.get('ABYSS_DESKTOP_PKG') or next(
    (str(p) for p in (ROOT / 'srcpkgs/abyss-desktop',
                      ROOT.parent / 'AbyssLinuxPMR/srcpkgs/abyss-desktop')
     if (p / 'files/session-audio').is_file()), '')
AUDIO = Path(os.environ.get('ABYSS_SESSION_AUDIO_SCRIPT') or (Path(PKG) / 'files/session-audio' if PKG else ''))
NAMES = ('pipewire', 'wireplumber', 'pipewire-pulse')
UID = '1000'
BUS = 'unix:path=/tmp/dbus-this-session,guid=1'
OTHER_BUS = 'unix:path=/tmp/dbus-old-session,guid=2'

# A process "runs" while its pid is listed in state/<name>; its environment is
# proc/<pid>/environ. The PipeWire stand-ins register themselves (pipewire also
# creates the socket); pkill unregisters, unless the name is in $STUBBORN and
# the signal is not KILL.
PGREP = r'''#!/bin/sh
for a; do name=$a; done
grep . "$FAKE/state/$name" 2>/dev/null
'''
PKILL = r'''#!/bin/sh
printf '%s\n' "pkill $*" >> "$FAKE/log"
for a; do name=$a; done
case " $STUBBORN " in *" $name "*) [ "$1" = -KILL ] || exit 0 ;; esac
rm -f "$FAKE/state/$name"
'''
START = r'''#!/bin/sh
name=${0##*/}
printf '%s\n' "$name $*" >> "$FAKE/log"
mkdir -p "$FAKE/proc/$$"
env | tr '\n' '\000' > "$FAKE/proc/$$/environ"
echo $$ >> "$FAKE/state/$name"
if [ "$name" = pipewire ]; then
    python3 -c 'import socket, sys; socket.socket(socket.AF_UNIX).bind(sys.argv[1])' "$XDG_RUNTIME_DIR/pipewire-0"
fi
'''


@unittest.skipUnless(AUDIO.is_file(), 'session-audio not found; set ABYSS_DESKTOP_PKG')
class SessionAudioTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='sa')
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name).resolve()
        self.bin = self.dir / 'bin'
        self.rt = self.dir / 'rt'
        for d in (self.bin, self.rt, self.dir / 'state', self.dir / 'proc'):
            d.mkdir(mode=0o700)
        self.stub('id', f'#!/bin/sh\necho {UID}\n')       # never root's 0 (CI runs as root)
        self.stub('pgrep', PGREP)
        self.stub('pkill', PKILL)
        for name in NAMES:
            self.stub(name, START)
        self.next_pid = 900001

    def stub(self, name, text):
        p = self.bin / name
        p.write_text(text)
        p.chmod(0o755)

    def env(self, **extra):
        env = {'PATH': f'{self.bin}:/usr/bin:/bin:/usr/sbin:/sbin', 'HOME': str(self.dir), 'LC_ALL': 'C',
               'FAKE': str(self.dir), 'ABYSS_PROC_DIR': str(self.dir / 'proc'),
               'XDG_RUNTIME_DIR': str(self.rt), 'DBUS_SESSION_BUS_ADDRESS': BUS}
        env.update(extra)
        return env

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

    def process(self, name, bus=BUS, rt=None):
        """A running process of an earlier login (or of this one)."""
        pid = str(self.next_pid)
        self.next_pid += 1
        (self.dir / 'proc' / pid).mkdir()
        (self.dir / 'proc' / pid / 'environ').write_bytes(
            f'HOME={self.dir}\0XDG_RUNTIME_DIR={rt or self.rt}\0DBUS_SESSION_BUS_ADDRESS={bus}\0'.encode())
        with open(self.dir / 'state' / name, 'a') as f:
            f.write(pid + '\n')
        return pid

    def live_socket(self):
        s = socket.socket(socket.AF_UNIX)
        s.bind(str(self.rt / 'pipewire-0'))
        self.addCleanup(s.close)

    def running(self, name):
        p = self.dir / 'state' / name
        return p.read_text().split() if p.exists() else []

    def assert_fresh_start(self, calls):
        starts = [c.strip() for c in calls if not c.startswith('pkill')]
        self.assertEqual(starts[0], 'pipewire')
        self.assertEqual(sorted(starts[1:]), ['pipewire-pulse', 'wireplumber'])
        for name in NAMES:
            self.assertEqual(len(self.running(name)), 1, name)
        self.assertTrue((self.rt / 'pipewire-0').is_socket())

    def assert_all_stopped_first(self, calls):
        kills = [c for c in calls if c.startswith('pkill')]
        self.assertEqual(kills[:3], [f'pkill -u {UID} -x {n}' for n in NAMES])
        self.assertLess(max(calls.index(k) for k in kills), calls.index('pipewire '))

    def test_first_login_starts_all_three(self):
        self.run_audio('start')
        calls = self.log()
        self.assertFalse([c for c in calls if c.startswith('pkill')])
        self.assert_fresh_start(calls)

    def test_running_for_this_session_is_kept(self):
        self.run_audio('start')
        self.log()
        before = {n: self.running(n) for n in NAMES}
        self.run_audio('start')                               # ~/.xinitrc after abyss-session
        self.run_audio()                                      # start is the default
        self.assertEqual(self.log(), [])
        self.assertEqual({n: self.running(n) for n in NAMES}, before)

    def test_previous_sessions_pipewire_is_replaced(self):
        # the reported case: pipewire and pipewire-pulse of the old session,
        # its socket gone with the old /run/user/UID, no wireplumber
        old = [self.process('pipewire', OTHER_BUS), self.process('pipewire-pulse', OTHER_BUS)]
        self.run_audio('start')
        calls = self.log()
        self.assert_all_stopped_first(calls)
        self.assert_fresh_start(calls)
        self.assertFalse(set(old) & {p for n in NAMES for p in self.running(n)})

    def test_other_session_with_a_live_socket_is_replaced(self):
        # the runtime directory survived (another login of the user kept it)
        for name in NAMES:
            self.process(name, OTHER_BUS)
        self.live_socket()
        self.run_audio('start')
        calls = self.log()
        self.assert_all_stopped_first(calls)
        self.assert_fresh_start(calls)

    def test_other_runtime_directory_is_replaced(self):
        for name in NAMES:
            self.process(name, BUS, rt='/run/user/elsewhere')
        self.live_socket()
        self.run_audio('start')
        self.assert_all_stopped_first(self.log())

    def test_missing_wireplumber_or_socket_restarts(self):
        for case in ('no wireplumber', 'no socket', 'no environ'):
            with self.subTest(case):
                for name in NAMES:
                    (self.dir / 'state' / name).unlink(missing_ok=True)
                (self.rt / 'pipewire-0').unlink(missing_ok=True)
                for name in NAMES:
                    if not (case == 'no wireplumber' and name == 'wireplumber'):
                        pid = self.process(name)
                        if case == 'no environ':
                            (self.dir / 'proc' / pid / 'environ').unlink()
                if case != 'no socket':
                    self.live_socket()
                self.log()
                self.run_audio('start')
                calls = self.log()
                self.assert_all_stopped_first(calls)
                self.assert_fresh_start(calls)

    def test_a_process_that_does_not_quit_is_killed(self):
        self.process('pipewire', OTHER_BUS)
        self.run_audio('start', STUBBORN='pipewire')
        calls = self.log()
        self.assertIn(f'pkill -KILL -u {UID} -x pipewire', calls)
        self.assert_fresh_start(calls)

    def test_stop_ends_this_sessions_audio_only(self):
        self.run_audio('start')
        self.log()
        self.run_audio('stop')
        self.assertEqual(self.log(), [f'pkill -u {UID} -x {n}' for n in NAMES])
        self.assertEqual([self.running(n) for n in NAMES], [[], [], []])
        # another session's PipeWire is left alone
        for name in NAMES:
            self.process(name, OTHER_BUS)
        self.run_audio('stop')
        self.assertEqual(self.log(), [])
        self.assertTrue(self.running('pipewire'))
        # and nothing running is fine
        for name in NAMES:
            (self.dir / 'state' / name).unlink()
        self.run_audio('stop')
        self.assertEqual(self.log(), [])

    def test_without_pipewire_installed_nothing_happens(self):
        system = '/usr/bin:/bin:/usr/sbin:/sbin'
        if shutil.which('pipewire', path=system):
            self.skipTest('pipewire is installed on this system')
        for name in NAMES:
            (self.bin / name).unlink()
        self.process('wireplumber', OTHER_BUS)
        for action in ('start', 'stop'):
            self.run_audio(action, PATH=f'{self.bin}:{system}')
        self.assertEqual(self.log(), [])

    def test_bad_argument(self):
        r = subprocess.run(['/bin/sh', str(AUDIO), 'restart'], env=self.env(), stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, text=True, timeout=30)
        self.assertEqual(r.returncode, 2)
        self.assertIn('usage', r.stdout)
        self.assertEqual(self.log(), [])


if __name__ == '__main__':
    unittest.main()
