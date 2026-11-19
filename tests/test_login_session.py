"""The first frames after the login screen (abyss-session and ~/.xinitrc).

Users keep the ~/.xinitrc and ~/.dwm/autostart.sh their image copied from
/etc/skel. Those of images before 27.3.3 draw the Abyss wallpaper with feh
before (and right after) dwm starts, so the user's own wallpaper appeared
only a second or two later, and dwm showed "dwm-6.8" until the status bar
named the root window. Covers:
  * abyss-session replaces a copy byte-identical to a version an Abyss image
    shipped (fixtures/skel: every version in AbyssLinux's history) with the
    current one from abyss-desktop, keeps <file>.abyss-old, and leaves edited,
    unknown and linked files alone;
  * it names the root window and draws the saved wallpaper before the user's
    ~/.xinitrc runs, and only for edited old files puts the legacy feh first
    in PATH, which turns exactly the old command into abyss-wallpaper;
  * the current .xinitrc names the root window and draws the wallpaper
    (in the foreground) before dwm starts, and not again after abyss-session;
  * PipeWire: abyss-session runs session-audio start before the user's
    ~/.xinitrc and session-audio stop when it ends, and turns the
    `pgrep ... || pipewire &` blocks of an edited older ~/.xinitrc into one
    session-audio call (keeping the rest, with ~/.xinitrc.abyss-audio-old);
    the current .xinitrc starts it with session-audio too;
  * the overlay and the abyss-desktop package carry the same files.
"""
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / 'fixtures/skel'
OVERLAY = ROOT / 'custom-overlay'
PKG = os.environ.get('ABYSS_DESKTOP_PKG') or next(
    (str(p) for p in (ROOT / 'srcpkgs/abyss-desktop',
                      ROOT.parent / 'AbyssLinuxPMR/srcpkgs/abyss-desktop')
     if (p / 'files/bin/abyss-session').is_file()), '')


def first(*paths):
    return next((Path(p) for p in paths if p and Path(p).is_file()), None)


SESSION = first(os.environ.get('ABYSS_SESSION'), OVERLAY / 'usr/local/bin/abyss-session',
                PKG and Path(PKG) / 'files/bin/abyss-session')
XINITRC = first(os.environ.get('ABYSS_SKEL_XINITRC'), OVERLAY / 'etc/skel/.xinitrc',
                PKG and Path(PKG) / 'files/skel/xinitrc')
AUTOSTART = first(os.environ.get('ABYSS_SKEL_AUTOSTART'), OVERLAY / 'etc/skel/.dwm/autostart.sh',
                  PKG and Path(PKG) / 'files/skel/autostart.sh')
LEGACY_FEH = first(os.environ.get('ABYSS_LEGACY_FEH'), PKG and Path(PKG) / 'files/legacy-feh')
DEFAULT = '/usr/share/backgrounds/abyss/abyss-wallpaper.jpg'
LEGACY_LINE = f'feh --bg-fill {DEFAULT} &\n'
AUDIO_LINE = ('[ -x /usr/libexec/abyss-desktop/session-audio ] && '
              '/usr/libexec/abyss-desktop/session-audio start')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fixtures(kind):
    return sorted((FIXTURES / kind).glob('*.sh'))


def listed_hashes():
    return set(re.findall(r'^\s*([0-9a-f]{64})\*', SESSION.read_text(), re.M))


class Stubs:
    """A temporary HOME and a PATH of logging stand-ins for the X tools."""

    def __init__(self, case, names):
        tmp = tempfile.TemporaryDirectory()
        case.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name).resolve()
        self.home = self.dir / 'home'
        self.bin = self.dir / 'bin'
        self.log = self.dir / 'log'
        (self.home / '.dwm').mkdir(parents=True)
        self.bin.mkdir()
        for name in names:
            self.stub(name)

    def stub(self, name, body=''):
        p = self.bin / name
        p.write_text('#!/bin/sh\n'
                     f'printf "%s\\n" "{name} $*" >> "{self.log}"\n' + body)
        p.chmod(0o755)

    def env(self, **extra):
        env = {'HOME': str(self.home), 'PATH': f'{self.bin}:/usr/bin:/bin:/usr/sbin:/sbin',
               'DBUS_SESSION_BUS_ADDRESS': 'unix:path=/nonexistent', 'LC_ALL': 'C',
               # never the installed one (it would end the host's PipeWire)
               'ABYSS_SESSION_AUDIO': str(self.dir / 'no-session-audio')}
        env.update(extra)
        return env

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def session_calls(self):
        # without abyss-session's background job, which may log at any time
        return [c for c in self.calls() if not c.startswith(('pgrep', 'abyss-wallpaper --legacy'))]


@unittest.skipUnless(SESSION, 'abyss-session not found; set ABYSS_SESSION')
class ShippedVersionsTest(unittest.TestCase):
    def test_session_lists_every_shipped_version(self):
        shipped = {sha(p.read_bytes()) for p in fixtures('xinitrc') + fixtures('autostart')}
        self.assertGreaterEqual(len(fixtures('xinitrc')), 7)
        self.assertGreaterEqual(len(fixtures('autostart')), 2)
        self.assertEqual(listed_hashes(), shipped)

    def test_no_shipped_version_draws_the_default_after_the_update(self):
        # the versions that drew the Abyss wallpaper themselves are all listed
        drawers = {sha(p.read_bytes()) for p in fixtures('xinitrc') + fixtures('autostart')
                   if f'feh --bg-fill {DEFAULT}' in p.read_text()}
        self.assertEqual(len(drawers), 6)                   # 5 .xinitrc + 1 autostart.sh
        self.assertLessEqual(drawers, listed_hashes())


@unittest.skipUnless((ROOT / '.git').exists() and OVERLAY.is_dir(), 'needs the AbyssLinux git history')
class HistoryTest(unittest.TestCase):
    def test_fixtures_cover_every_version_in_git_history(self):
        for kind, path in (('xinitrc', 'custom-overlay/etc/skel/.xinitrc'),
                           ('autostart', 'custom-overlay/etc/skel/.dwm/autostart.sh')):
            with self.subTest(path):
                commits = subprocess.run(['git', '-C', str(ROOT), 'log', '--format=%H', '--follow', '--', path],
                                         stdout=subprocess.PIPE, text=True, check=True).stdout.split()
                self.assertTrue(commits)
                versions = set()
                for commit in commits:
                    show = subprocess.run(['git', '-C', str(ROOT), 'show', f'{commit}:{path}'],
                                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                    if show.returncode == 0:
                        versions.add(sha(show.stdout))
                current = sha((ROOT / path).read_bytes())
                known = {sha(p.read_bytes()) for p in fixtures(kind)}
                # every committed version is a fixture, or the current file
                self.assertEqual(versions - known - {current}, set())


@unittest.skipUnless(SESSION and shutil.which('sha256sum'), 'abyss-session or sha256sum not found')
class MigrationTest(unittest.TestCase):
    """abyss-session run as LightDM runs it, with a stand-in skel directory."""

    def setUp(self):
        self.s = Stubs(self, ['xsetroot', 'abyss-wallpaper', 'pgrep', 'dwm', 'dbus-run-session'])
        self.skel = self.s.dir / 'skel'
        (self.skel / '.dwm').mkdir(parents=True)
        (self.skel / '.xinitrc').write_text(f'echo "current xinitrc" >> "{self.s.log}"\n')
        (self.skel / '.dwm/autostart.sh').write_text('#!/bin/sh\n# current autostart\n')

    def run_session(self):
        r = subprocess.run(['/bin/sh', str(SESSION)], env=self.s.env(ABYSS_SKEL_DIR=str(self.skel),
                                                                     ABYSS_LEGACY_DIR=str(self.s.dir / 'nolegacy')),
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stdout)
        return r.stdout

    def put(self, rel, data, mode=0o755):
        p = self.s.home / rel
        p.write_bytes(data)
        p.chmod(mode)
        return p

    def test_every_shipped_xinitrc_is_replaced_with_a_backup(self):
        for fx in fixtures('xinitrc'):
            with self.subTest(fx.name):
                old = fx.read_bytes()
                p = self.put('.xinitrc', old, 0o644)
                (self.s.home / '.xinitrc.abyss-old').unlink(missing_ok=True)
                out = self.run_session()
                self.assertEqual(p.read_bytes(), (self.skel / '.xinitrc').read_bytes())
                self.assertEqual((self.s.home / '.xinitrc.abyss-old').read_bytes(), old)
                self.assertEqual(p.stat().st_mode & 0o777, 0o755)
                self.assertIn('updated ~/.xinitrc', out)
                self.assertEqual(self.s.session_calls()[-1], 'current xinitrc')      # the new one ran
                self.assertEqual([f for f in os.listdir(self.s.home) if '.xinitrc.' in f and not f.endswith('abyss-old')], [])

    def test_shipped_autostart_is_replaced(self):
        old = next(p.read_bytes() for p in fixtures('autostart') if b'feh' in p.read_bytes())
        p = self.put('.dwm/autostart.sh', old)
        self.run_session()
        self.assertEqual(p.read_bytes(), (self.skel / '.dwm/autostart.sh').read_bytes())
        self.assertEqual((self.s.home / '.dwm/autostart.sh.abyss-old').read_bytes(), old)

    def test_edited_unknown_and_linked_files_are_kept(self):
        shipped = fixtures('xinitrc')[0].read_bytes()
        cases = {'edited': shipped + b'\n# my change\n', 'unknown': b'exec dwm\n'}
        for name, data in cases.items():
            with self.subTest(name):
                p = self.put('.xinitrc', data)
                self.run_session()
                if name == 'edited':     # only its PipeWire lines change (AudioMigrationTest)
                    self.assertTrue(p.read_bytes().endswith(b'\n# my change\n'))
                    self.assertNotEqual(p.read_bytes(), (self.skel / '.xinitrc').read_bytes())
                else:
                    self.assertEqual(p.read_bytes(), data)
                self.assertFalse((self.s.home / '.xinitrc.abyss-old').exists())
        with self.subTest('symlink'):
            target = self.s.dir / 'my-xinitrc'
            target.write_bytes(shipped)
            (self.s.home / '.xinitrc').unlink()
            (self.s.home / '.xinitrc').symlink_to(target)
            self.run_session()
            self.assertTrue((self.s.home / '.xinitrc').is_symlink())
            self.assertEqual(target.read_bytes(), shipped)
            self.assertFalse((self.s.home / '.xinitrc.abyss-old').exists())

    def test_current_file_and_missing_skel_change_nothing(self):
        p = self.put('.xinitrc', (self.skel / '.xinitrc').read_bytes())
        self.assertNotIn('updated', self.run_session())
        self.assertFalse((self.s.home / '.xinitrc.abyss-old').exists())
        shutil.rmtree(self.skel)
        old = fixtures('xinitrc')[0].read_bytes()
        self.put('.xinitrc', old)
        r = subprocess.run(['/bin/sh', str(SESSION)], env=self.s.env(ABYSS_SKEL_DIR=str(self.skel)),
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30)
        self.assertEqual(p.read_bytes(), old, r.stdout)

    def test_without_xinitrc_the_package_one_runs(self):
        self.run_session()
        self.assertEqual(self.s.session_calls()[-1], 'current xinitrc')


@unittest.skipUnless(SESSION, 'abyss-session not found; set ABYSS_SESSION')
class SessionOrderTest(unittest.TestCase):
    """Before the user's ~/.xinitrc: the root window name, then the wallpaper."""

    def setUp(self):
        self.s = Stubs(self, ['xsetroot', 'pgrep'])
        self.s.stub('abyss-wallpaper')
        self.legacy = self.s.dir / 'legacy'
        self.legacy.mkdir()
        (self.legacy / 'feh').write_text('#!/bin/sh\n')
        (self.legacy / 'feh').chmod(0o755)

    def run_session(self, xinitrc):
        (self.s.home / '.xinitrc').write_text(xinitrc + f'\necho "xinitrc PATH=$PATH DRAWN=$ABYSS_WALLPAPER_DRAWN" >> "{self.s.log}"\n')
        r = subprocess.run(['/bin/sh', str(SESSION)], env=self.s.env(ABYSS_SKEL_DIR=str(self.s.dir / 'noskel'),
                                                                     ABYSS_LEGACY_DIR=str(self.legacy)),
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stdout)
        return self.s.session_calls()

    def test_name_and_wallpaper_come_before_the_users_file(self):
        calls = self.run_session('# my own session\n')
        self.assertEqual(calls[:2], ['xsetroot -name  ', 'abyss-wallpaper '])
        self.assertTrue(calls[2].startswith('xinitrc '), calls)
        self.assertIn('DRAWN=1', calls[2])
        self.assertNotIn(str(self.legacy), calls[2])           # no legacy feh for other files

    def test_edited_legacy_file_gets_the_legacy_feh(self):
        for where in ('.xinitrc', '.dwm/autostart.sh'):
            with self.subTest(where):
                if where == '.xinitrc':
                    calls = self.run_session('# edited\n' + LEGACY_LINE)
                else:
                    (self.s.home / '.dwm/autostart.sh').write_text('# edited\n' + LEGACY_LINE)
                    calls = self.run_session('# my own session\n')
                    (self.s.home / '.dwm/autostart.sh').unlink()
                self.assertIn(f'PATH={self.legacy}:', calls[-1])


@unittest.skipUnless(LEGACY_FEH, 'abyss-desktop package not found; set ABYSS_DESKTOP_PKG')
class LegacyFehTest(unittest.TestCase):
    def setUp(self):
        self.s = Stubs(self, ['abyss-wallpaper'])

    def feh(self, *args, **env):
        return subprocess.run(['/bin/sh', str(LEGACY_FEH), *args], env=self.s.env(**env),
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30)

    def test_only_the_old_command_draws_the_saved_choice(self):
        self.assertEqual(self.feh('--bg-fill', DEFAULT).returncode, 0)
        self.assertEqual(self.s.calls(), ['abyss-wallpaper '])
        for args in (['--no-fehbg', '--bg-fill', DEFAULT], ['--bg-fill', '/home/me/pic.jpg'],
                     ['--bg-max', DEFAULT], [DEFAULT], ['--bg-fill', DEFAULT, '--no-xinerama']):
            with self.subTest(args):
                self.feh(*args)                                # runs /usr/bin/feh (absent here)
                self.assertEqual(self.s.calls(), ['abyss-wallpaper '])

    def test_no_loop_through_abyss_wallpaper(self):
        self.feh('--bg-fill', DEFAULT, ABYSS_LEGACY_FEH='1')
        self.assertEqual(self.s.calls(), [])

    def test_wallpaper_never_matches_the_old_command(self):
        # abyss-wallpaper always passes --no-fehbg, so its feh is never redirected
        wp = first(OVERLAY / 'usr/local/bin/abyss-wallpaper', PKG and Path(PKG) / 'files/bin/abyss-wallpaper')
        self.assertIn('exec feh --no-fehbg "$fit" "$img"', wp.read_text())


@unittest.skipUnless(XINITRC, 'skel .xinitrc not found')
class XinitrcOrderTest(unittest.TestCase):
    """The current .xinitrc, run with logging stand-ins (startx and LightDM)."""
    NAMES = ['xsetroot', 'abyss-wallpaper', 'dwm', 'abyss-display', 'abyss-scale', 'xset', 'xrdb',
             'wmname', 'abyss-setup', 'xdg-user-dirs-update', 'pipewire', 'wireplumber',
             'pipewire-pulse', 'xss-lock', 'pgrep', 'pkill', 'dbus-run-session']

    def run_xinitrc(self, **env):
        s = Stubs(self, self.NAMES)
        r = subprocess.run(['/bin/sh', str(XINITRC)], env=s.env(XDG_RUNTIME_DIR=str(s.dir), **env),
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stdout)
        return [c.split(' ')[0] if not c.startswith('xsetroot') else c for c in s.calls()]

    def test_wallpaper_and_name_before_dwm(self):
        calls = self.run_xinitrc()
        self.assertIn('dwm', calls)                        # (background jobs may log later)
        self.assertIn('abyss-wallpaper', calls)
        self.assertIn('xsetroot -name  ', calls)
        self.assertLess(calls.index('xsetroot -name  '), calls.index('dwm'))
        self.assertLess(calls.index('abyss-wallpaper'), calls.index('dwm'))
        # drawn after the screen's mode and scale are set
        self.assertLess(calls.index('abyss-display'), calls.index('abyss-wallpaper'))

    def test_not_drawn_twice_after_abyss_session(self):
        calls = self.run_xinitrc(ABYSS_WALLPAPER_DRAWN='1')
        self.assertNotIn('abyss-wallpaper', calls)
        self.assertIn('dwm', calls)

    def test_wallpaper_is_drawn_in_the_foreground(self):
        text = XINITRC.read_text()
        self.assertNotRegex(text, r'abyss-wallpaper\s*&')
        self.assertNotIn('feh ', text)
        self.assertLess(text.index('xsetroot -name " "'), text.index('dwm-statusbar &'))

    def test_audio_is_started_by_session_audio(self):
        text = XINITRC.read_text()
        self.assertEqual(text.count(AUDIO_LINE), 1)
        self.assertLess(text.index(AUDIO_LINE), text.index('exec dwm'))
        for name in ('pipewire', 'wireplumber', 'pipewire-pulse'):
            self.assertNotIn(f'-x {name}', text)
            self.assertNotRegex(text, rf'(?m)^\s*{name} &')


def strip_audio_blocks(text):
    """The old file with its PipeWire start blocks replaced the way abyss-session does."""
    out, done = [], False
    lines = text.split('\n')
    i = 0
    while i < len(lines):
        m = re.fullmatch(r'if command -v ([a-z-]+) >/dev/null 2>&1 && ! pgrep (?:-u "\$\(id -u\)" )?-x \1 '
                         r'>/dev/null 2>&1; then', lines[i])
        if m and m.group(1) in ('pipewire', 'wireplumber', 'pipewire-pulse') and \
                lines[i + 1:i + 3] == [f'    {m.group(1)} &', 'fi']:
            if not done:
                out.append(AUDIO_LINE)
            done = True
            i += 3
            continue
        out.append(lines[i])
        i += 1
    return '\n'.join(out)


@unittest.skipUnless(SESSION, 'abyss-session not found; set ABYSS_SESSION')
class AudioMigrationTest(unittest.TestCase):
    """Edited ~/.xinitrc files of every version: their PipeWire lines only."""

    def setUp(self):
        self.s = Stubs(self, ['xsetroot', 'abyss-wallpaper', 'pgrep', 'pkill', 'dwm', 'dbus-run-session',
                              'pipewire', 'wireplumber', 'pipewire-pulse'])
        self.skel = self.s.dir / 'skel'
        self.skel.mkdir()
        (self.skel / '.xinitrc').write_text('# current\n')
        self.audio = self.s.bin / 'session-audio'
        self.s.stub('session-audio')

    def run_session(self):
        r = subprocess.run(['/bin/sh', str(SESSION)],
                           env=self.s.env(ABYSS_SKEL_DIR=str(self.skel), ABYSS_SESSION_AUDIO=str(self.audio),
                                          ABYSS_LEGACY_DIR=str(self.s.dir / 'nolegacy')),
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stdout)
        return r.stdout

    def test_every_edited_version_starts_audio_with_session_audio(self):
        for fx in fixtures('xinitrc'):
            with self.subTest(fx.name):
                old = '# my own line\n' + fx.read_text().replace('exec dwm', 'exec dwm  # edited')
                p = self.s.home / '.xinitrc'
                p.write_text(old)
                p.chmod(0o700)
                backup = self.s.home / '.xinitrc.abyss-audio-old'
                backup.unlink(missing_ok=True)
                self.s.log.unlink(missing_ok=True)
                out = self.run_session()
                new = p.read_text()
                self.assertEqual(new, strip_audio_blocks(old))
                self.assertEqual(new.count(AUDIO_LINE), 1)
                self.assertNotRegex(new, r'(?m)^\s*(pipewire|wireplumber|pipewire-pulse) &')
                self.assertIn('# my own line', new)
                self.assertEqual(backup.read_text(), old)
                self.assertEqual(p.stat().st_mode & 0o777, 0o700)
                self.assertIn('session-audio', out)
                self.assertEqual([f for f in os.listdir(self.s.home) if f.startswith('.xinitrc.')
                                  and f != '.xinitrc.abyss-audio-old'], [])
                calls = self.s.session_calls()
                self.assertLess(calls.index('session-audio start'), calls.index('dwm '))
                self.assertEqual(calls[-1], 'session-audio stop')
                # a second login changes nothing
                backup.unlink()
                self.assertNotIn('abyss-audio-old', self.run_session())
                self.assertEqual(p.read_text(), new)
                self.assertFalse(backup.exists())

    def test_other_audio_lines_and_links_are_kept(self):
        cases = {'own pipewire line': '#!/bin/sh\npipewire &\nexec dwm\n',
                 'changed block': '#!/bin/sh\nif ! pgrep -x pipewire; then\n    pipewire &\nfi\nexec dwm\n',
                 'no audio': '#!/bin/sh\nexec dwm\n'}
        for name, data in cases.items():
            with self.subTest(name):
                p = self.s.home / '.xinitrc'
                p.write_text(data)
                self.run_session()
                self.assertEqual(p.read_text(), data)
                self.assertFalse((self.s.home / '.xinitrc.abyss-audio-old').exists())
        with self.subTest('symlink'):
            target = self.s.dir / 'my-xinitrc'
            old = '# mine\n' + fixtures('xinitrc')[0].read_text()
            target.write_text(old)
            (self.s.home / '.xinitrc').unlink()
            (self.s.home / '.xinitrc').symlink_to(target)
            self.run_session()
            self.assertEqual(target.read_text(), old)
            self.assertFalse((self.s.home / '.xinitrc.abyss-audio-old').exists())


@unittest.skipUnless(SESSION, 'abyss-session not found; set ABYSS_SESSION')
class SessionAudioCallTest(unittest.TestCase):
    """abyss-session starts the session's PipeWire first and ends it after dwm."""

    def setUp(self):
        self.s = Stubs(self, ['xsetroot', 'abyss-wallpaper', 'pgrep'])
        self.audio = self.s.bin / 'session-audio'

    def run_session(self, xinitrc):
        (self.s.home / '.xinitrc').write_text(xinitrc)
        return subprocess.run(['/bin/sh', str(SESSION)],
                              env=self.s.env(ABYSS_SKEL_DIR=str(self.s.dir / 'noskel'),
                                             ABYSS_SESSION_AUDIO=str(self.audio)),
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30)

    def test_start_before_and_stop_after_the_session(self):
        self.s.stub('session-audio')
        r = self.run_session(f'echo "dwm runs" >> "{self.s.log}"\nexit 3\n')
        self.assertEqual(r.returncode, 3, r.stdout)          # the session's own status
        self.assertEqual(self.s.session_calls()[-3:], ['session-audio start', 'dwm runs', 'session-audio stop'])

    def test_without_session_audio(self):
        r = self.run_session(f'echo "dwm runs" >> "{self.s.log}"\n')
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(self.s.session_calls()[-1], 'dwm runs')


@unittest.skipUnless(OVERLAY.is_dir() and PKG, 'needs the AbyssLinux overlay and the abyss-desktop package')
class OverlayPackageTest(unittest.TestCase):
    def test_same_files_in_image_and_package(self):
        pairs = [('usr/local/bin/abyss-session', 'files/bin/abyss-session'),
                 ('usr/local/bin/abyss-wallpaper', 'files/bin/abyss-wallpaper'),
                 ('usr/local/bin/dwm-statusbar', 'files/bin/dwm-statusbar'),
                 ('etc/skel/.xinitrc', 'files/skel/xinitrc'),
                 ('etc/skel/.dwm/autostart.sh', 'files/skel/autostart.sh')]
        for overlay, pkg in pairs:
            with self.subTest(overlay):
                self.assertEqual((OVERLAY / overlay).read_bytes(), (Path(PKG) / pkg).read_bytes())

    def test_template_installs_skel_and_legacy_feh(self):
        t = (Path(PKG) / 'template').read_text()
        self.assertIn('usr/share/abyss/skel .xinitrc', t)
        self.assertIn('usr/share/abyss/skel/.dwm autostart.sh', t)
        self.assertIn('usr/libexec/abyss-desktop/legacy feh', t)
        self.assertIn('vinstall ${FILESDIR}/session-audio 755 usr/libexec/abyss-desktop', t)


if __name__ == '__main__':
    unittest.main()
