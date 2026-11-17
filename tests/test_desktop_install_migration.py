"""abyss-desktop's INSTALL post step on an existing system, run the way xbps
runs it: wrapped in the header xbps-src generates, with the arguments xbps
passes ($1=post $2=pkgname $3=version $4=update $5=conf $6=arch) and the
system root as the working directory (here a temporary directory).

Covers the one-off migrations:
  * /etc/profile.d/99-void-dev-cli.sh (image-only copy of the shell helpers)
    becomes a stub that loads the packaged zz-abyss-cli.sh, but only when it
    is byte-identical to a version an Abyss image shipped;
  * the stock elogind runit link is removed once (D-Bus starts elogind);
  * chronyd (time synchronisation) is enabled once, unless another NTP
    client is enabled, and never again after the user disabled it.
The /usr/local/bin wrappers are covered by test_local_bin_wrappers.py.
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
PKG = os.environ.get('ABYSS_DESKTOP_PKG') or next(
    (str(p) for p in (ROOT / 'srcpkgs/abyss-desktop',
                      ROOT.parent / 'AbyssLinuxPMR/srcpkgs/abyss-desktop')
     if (p / 'files/zz-abyss-cli.sh').is_file()), '')
SHIPPED = sorted((Path(__file__).resolve().parent / 'fixtures/99-void-dev-cli').glob('*.sh'))
OLD = 'etc/profile.d/99-void-dev-cli.sh'
LINK = 'etc/runit/runsvdir/default/elogind'
STAMP = 'var/lib/abyss-desktop/elogind-dbus-activated'
CHRONY = 'etc/runit/runsvdir/default/chronyd'
NTP_STAMP = 'var/lib/abyss-desktop/time-sync-enabled'

# Same prologue as void-packages common/hooks/post-install/04-create-xbps-metadata-scripts.sh
HEADER = '''#!/bin/sh
export PATH="/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin"
TRIGGERSDIR="./usr/libexec/xbps-triggers"
ACTION="$1"
PKGNAME="$2"
VERSION="$3"
UPDATE="$4"
CONF_FILE="$5"
ARCH="$6"
'''


@unittest.skipUnless(PKG and shutil.which('sha256sum'), 'abyss-desktop package or sha256sum not found; set ABYSS_DESKTOP_PKG')
class InstallMigrationTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        (self.root / 'etc/profile.d').mkdir(parents=True)
        (self.root / 'etc/runit/runsvdir/default').mkdir(parents=True)
        self.script = self.root.parent / f'{self.root.name}.INSTALL'
        self.script.write_text(HEADER + (Path(PKG) / 'INSTALL').read_text() + '\nexit 0\n')
        self.addCleanup(self.script.unlink)
        # what unpacking the package puts on disk before INSTALL post runs
        helper = self.root / 'usr/libexec/abyss-desktop/local-bin-wrappers'
        helper.parent.mkdir(parents=True)
        shutil.copy(Path(PKG) / 'files/local-bin-wrappers', helper)

    def install(self):
        result = subprocess.run(['/bin/sh', str(self.script), 'post', 'abyss-desktop', '1.0_30', 'yes', 'no', 'aarch64'],
                                cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout)
        return result.stdout

    def path(self, rel):
        return self.root / rel

    # -- shell helpers ---------------------------------------------------
    def test_every_shipped_version_is_known_to_install(self):
        listed = set(re.findall(r'^\s*([0-9a-f]{64})\*', (Path(PKG) / 'INSTALL').read_text(), re.M))
        shipped = {hashlib.sha256(p.read_bytes()).hexdigest() for p in SHIPPED}
        self.assertEqual(len(shipped), 4)
        self.assertEqual(listed, shipped)

    def test_untouched_old_copy_becomes_stub(self):
        for fixture in SHIPPED:
            with self.subTest(fixture.name):
                shutil.copy(fixture, self.path(OLD))
                self.install()
                stub = self.path(OLD).read_text()
                self.assertTrue(stub.startswith('# managed by abyss-desktop'), stub)
                self.assertIn('. /etc/profile.d/zz-abyss-cli.sh', stub)
                self.assertEqual(self.path(OLD).stat().st_mode & 0o777, 0o644)
                self.assertEqual([p.name for p in self.path('etc/profile.d').iterdir()], ['99-void-dev-cli.sh'])
                again = self.install()
                self.assertEqual(self.path(OLD).read_text(), stub)
                self.assertNotIn('99-void-dev-cli', again)

    def test_edited_old_copy_is_left_alone(self):
        edited = SHIPPED[-1].read_text() + "alias ll='ls -l'\n"
        self.path(OLD).write_text(edited)
        out = self.install()
        self.assertEqual(self.path(OLD).read_text(), edited)
        self.assertIn('kept your edited /etc/profile.d/99-void-dev-cli.sh', out)

    def test_no_old_copy_creates_nothing(self):
        self.install()
        self.assertFalse(self.path(OLD).exists())

    def test_symlinked_old_copy_is_left_alone(self):
        self.path('etc/profile.d/mine.sh').write_text('true\n')
        self.path(OLD).symlink_to('mine.sh')
        self.install()
        self.assertTrue(self.path(OLD).is_symlink())
        self.assertEqual(self.path('etc/profile.d/mine.sh').read_text(), 'true\n')

    def test_packaged_helpers_load_in_an_interactive_shell(self):
        helpers = Path(PKG) / 'files/zz-abyss-cli.sh'
        out = subprocess.run(['bash', '--norc', '--noprofile', '-i', '-c',
                              f'. "{helpers}"; . "{helpers}"; type -t update upgrade install remove cleanup abyss_priv; echo "$PATH"'],
                             env={'HOME': str(self.root), 'PATH': '/usr/bin:/bin', 'PS1': '$ '},
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=30).stdout.split('\n')
        self.assertEqual(out[:6], ['function'] * 6)
        path = out[6].split(':')
        self.assertEqual(path.count('/usr/local/bin'), 1, out[6])       # loaded twice, added once
        self.assertEqual(path.count(f'{self.root}/.local/bin'), 1, out[6])

    # -- elogind ---------------------------------------------------------
    def test_stock_elogind_link_is_removed_once(self):
        self.path(LINK).symlink_to('/etc/sv/elogind')
        out = self.install()
        self.assertFalse(os.path.lexists(self.path(LINK)))
        self.assertTrue(self.path(STAMP).is_file())
        self.assertIn('disabled the elogind runit service', out)
        # the user enables it again on purpose: later updates keep it
        self.path(LINK).symlink_to('/etc/sv/elogind')
        self.assertNotIn('elogind', self.install())
        self.assertTrue(self.path(LINK).is_symlink())

    def test_other_service_links_are_untouched(self):
        for name in ('dbus', 'polkit', 'lightdm', 'NetworkManager'):
            self.path(f'etc/runit/runsvdir/default/{name}').symlink_to(f'/etc/sv/{name}')
        self.path(LINK).symlink_to('/etc/sv/elogind')
        self.install()
        self.assertEqual(sorted(p.name for p in self.path('etc/runit/runsvdir/default').iterdir()),
                         ['NetworkManager', 'dbus', 'lightdm', 'polkit'])

    def test_non_stock_elogind_link_is_kept(self):
        self.path(LINK).symlink_to('/etc/sv/my-elogind')
        self.install()
        self.assertTrue(self.path(LINK).is_symlink())
        self.assertTrue(self.path(STAMP).is_file())

    def test_no_link_only_records_the_migration(self):
        self.install()
        self.assertTrue(self.path(STAMP).is_file())
        self.path(LINK).symlink_to('/etc/sv/elogind')      # enabled later by the user
        self.install()
        self.assertTrue(self.path(LINK).is_symlink())

    # -- time synchronisation ---------------------------------------------
    def with_chrony(self):
        run = self.path('etc/sv/chronyd/run')
        run.parent.mkdir(parents=True)
        run.write_text('#!/bin/sh\nexec chronyd -n -u chrony ${OPTS}\n')

    def test_chronyd_is_enabled_once_with_the_abyss_configuration(self):
        self.with_chrony()
        out = self.install()
        self.assertEqual(os.readlink(self.path(CHRONY)), '/etc/sv/chronyd')
        self.assertIn('enabled chronyd', out)
        self.assertTrue(self.path(NTP_STAMP).is_file())
        conf = self.path('etc/sv/chronyd/conf').read_text()
        self.assertIn('OPTS="-f /usr/share/abyss/chrony.conf"', conf)
        # the runit run script sources it: the option is set only while the file exists
        for exists, want in ((True, '-f /usr/share/abyss/chrony.conf'), (False, '')):
            abyss_conf = self.root / 'abyss-chrony.conf'
            if exists:
                abyss_conf.write_text('')
            elif abyss_conf.exists():
                abyss_conf.unlink()
            sourced = self.root / 'conf.sh'
            sourced.write_text(conf.replace('/usr/share/abyss/chrony.conf', str(abyss_conf)))
            got = subprocess.run(['sh', '-c', 'OPTS=; . "$1"; printf %s "$OPTS"', 'sh', str(sourced)],
                                 stdout=subprocess.PIPE, text=True).stdout
            self.assertEqual(got, want.replace('/usr/share/abyss/chrony.conf', str(abyss_conf)))
        self.assertNotIn('chronyd', self.install())            # a second update does nothing

    def test_disabled_chronyd_stays_disabled(self):
        self.with_chrony()
        self.install()
        self.path(CHRONY).unlink()                               # the user turns it off
        self.install()
        self.assertFalse(os.path.lexists(self.path(CHRONY)))

    def test_another_ntp_client_is_respected(self):
        self.with_chrony()
        for other in ('openntpd', 'ntpd', 'isc-ntpd', 'busybox-ntpd'):
            with self.subTest(other):
                link = self.path(f'etc/runit/runsvdir/default/{other}')
                link.symlink_to(f'/etc/sv/{other}')
                if self.path(NTP_STAMP).exists():
                    self.path(NTP_STAMP).unlink()
                out = self.install()
                self.assertFalse(os.path.lexists(self.path(CHRONY)))
                self.assertFalse(self.path('etc/sv/chronyd/conf').exists())
                self.assertIn(f'left to the enabled {other} service', out)
                self.assertTrue(self.path(NTP_STAMP).is_file())
                link.unlink()

    def test_an_existing_chronyd_conf_is_kept(self):
        self.with_chrony()
        self.path('etc/sv/chronyd/conf').write_text('OPTS="-r"\n')
        self.install()
        self.assertEqual(self.path('etc/sv/chronyd/conf').read_text(), 'OPTS="-r"\n')
        self.assertTrue(self.path(CHRONY).is_symlink())

    def test_without_chrony_nothing_is_recorded(self):
        self.install()
        self.assertFalse(os.path.lexists(self.path(CHRONY)))
        self.assertFalse(self.path(NTP_STAMP).exists())         # tried again once chrony is there
        self.with_chrony()
        self.install()
        self.assertTrue(self.path(CHRONY).is_symlink())

    @unittest.skipUnless(Path('/proc/self/comm').exists(), 'needs Linux /proc')
    def test_running_runit_elogind_is_not_stopped(self):
        # a long-lived process named "elogind" that runsv reports as its child
        fake = self.root / 'elogind'
        shutil.copy(shutil.which('sleep'), fake)
        proc = subprocess.Popen([str(fake), '30'])
        self.addCleanup(proc.kill)
        sup = self.path('etc/sv/elogind/supervise')
        sup.mkdir(parents=True)
        (sup / 'pid').write_text(f'{proc.pid}\n')
        self.path(LINK).symlink_to('/etc/sv/elogind')
        self.install()
        self.assertTrue(self.path(LINK).is_symlink())
        self.assertFalse(self.path(STAMP).exists())     # tried again on the next update
        proc.kill(); proc.wait()
        (sup / 'pid').write_text('')                      # runit lost the race: the loop state
        self.install()
        self.assertFalse(os.path.lexists(self.path(LINK)))
        self.assertTrue(self.path(STAMP).is_file())


@unittest.skipUnless((ROOT / '.git').exists() and (ROOT / 'custom-overlay').is_dir(), 'needs the AbyssLinux git history')
class ShippedFixturesTest(unittest.TestCase):
    def test_fixtures_cover_every_version_in_git_history(self):
        path = 'custom-overlay/etc/profile.d/99-void-dev-cli.sh'
        commits = subprocess.run(['git', '-C', str(ROOT), 'log', '--format=%H', '--', path],
                                 stdout=subprocess.PIPE, text=True, check=True).stdout.split()
        versions = set()
        for commit in commits:
            show = subprocess.run(['git', '-C', str(ROOT), 'show', f'{commit}:{path}'], stdout=subprocess.PIPE)
            if show.returncode == 0:                       # the deleting commit has no content
                versions.add(hashlib.sha256(show.stdout).hexdigest())
        self.assertEqual(versions, {hashlib.sha256(p.read_bytes()).hexdigest() for p in SHIPPED})


if __name__ == '__main__':
    unittest.main()
