"""Disk upkeep (abyss-desktop): package cache cleaning after installs and
upgrades, the weekly TRIM service and its one-time enabling.

  * disk-care clean-cache removes the obsolete cached packages (xbps-remove
    -O), prints how much that freed, and only names orphan packages;
  * upgrade/install (zz-abyss-cli.sh) and abyss-software's install run it
    after a successful xbps-install, never after a failed one;
  * disk-care trim-service: TRIM is due a week after the last run (the stamp
    holds its epoch), at once when the stamp is missing, unreadable or dated
    in the future, never on the live ISO; one line per run in the log;
  * INSTALL enables abyss-fstrim once and leaves a user's removal alone.

xbps, fstrim and friends are shell stubs; nothing needs root.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
PKG = os.environ.get('ABYSS_DESKTOP_PKG') or next(
    (str(p) for p in (ROOT / 'srcpkgs/abyss-desktop',
                      ROOT.parent / 'AbyssLinuxPMR/srcpkgs/abyss-desktop')
     if (p / 'files/disk-care').is_file()), '')
CARE = Path(PKG) / 'files/disk-care'
PROFILE = Path(PKG) / 'files/zz-abyss-cli.sh'
SOFTWARE = Path(PKG) / 'files/bin/abyss-software'
TOOLS = ('sh bash awk sed head tail cat cp rm mv mkdir tr cut sort grep sleep mktemp tee env '
         'dirname basename chmod find touch du date paste wc ls nice readlink ln').split()
DAY = 86400

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

# xbps-remove -O deletes the cached files named in $HOME/obsolete.
XBPS_REMOVE = r'''printf 'remove %s\n' "$*" >> "$HOME/xbps.log"
case " $* " in *" -O "*)
    while read -r f; do rm -f "$ABYSS_XBPS_CACHE/$f"; done < "$HOME/obsolete" 2>/dev/null ;;
esac
exit 0'''
XBPS_QUERY = r'''if [ "$1" = -O ]; then cat "$HOME/orphans" 2>/dev/null; exit 0; fi
if [ "$1" = -l ]; then exit 0; fi
if [ "$1" = -R ]; then echo "pkgver: $2-1.0_1"; exit 0; fi
grep -qx "$1" "$HOME/installed" 2>/dev/null'''
XBPS_INSTALL = r'''printf '%s\n' "$*" >> "$HOME/xbps.log"
case " $* " in *" -S "*) exit 0 ;; *" -n "*) exit 0 ;; esac
[ -e "$HOME/install-fail" ] && exit 19
for a; do case $a in -*) ;; *) echo "$a" >> "$HOME/installed" ;; esac; done
exit 0'''


@unittest.skipUnless(CARE.is_file(), 'abyss-desktop disk-care not found; set ABYSS_DESKTOP_PKG')
class Stubbed(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        for tool in TOOLS:
            found = shutil.which(tool, path='/usr/bin:/bin:/usr/sbin:/sbin')
            if found:
                (self.bin / tool).symlink_to(found)
        self.cache = self.root / 'cache'
        self.cache.mkdir()
        self.stub('xbps-remove', XBPS_REMOVE)
        self.stub('xbps-query', XBPS_QUERY)
        self.stub('xbps-install', XBPS_INSTALL)
        self.stub('pgrep', 'exit 1')
        self.stub('id', '[ "$1" = -u ] && { echo 0; exit; }; echo uid=0')
        self.stub('uname', 'echo aarch64')
        self.stub('abyss-priv', 'exec "$@"')
        self.env = {'HOME': str(self.root), 'PATH': str(self.bin), 'TMPDIR': str(self.root),
                    'ABYSS_XBPS_CACHE': str(self.cache), 'ABYSS_RETRY_PAUSE': '0', 'ABYSS_LOCK_POLL': '0',
                    'ABYSS_SYNC_STAMP': str(self.root / 'synced')}

    def stub(self, name, body):
        path = self.bin / name
        if path.is_symlink() or path.exists():
            path.unlink()
        path.write_text('#!/bin/sh\n' + body + '\n')
        path.chmod(0o755)

    def write(self, name, text):
        (self.root / name).write_text(text)

    def log(self, name):
        path = self.root / name
        return path.read_text().splitlines() if path.exists() else []

    def run_cmd(self, argv, env=None, stdin=None):
        result = subprocess.run(argv, env={**self.env, **(env or {})}, cwd=self.root, input=stdin,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=60)
        self.status = result.returncode
        return result.stdout

    def care(self, *args, env=None):
        return self.run_cmd(['/bin/sh', str(CARE), *args], env)

    def cached(self, name, mib):
        (self.cache / name).write_bytes(b'x' * (mib * 1024 * 1024))


class CleanCacheTest(Stubbed):
    def test_obsolete_packages_are_removed_and_the_freed_space_is_reported(self):
        self.cached('foo-1.0_1.aarch64.xbps', 3)
        self.cached('foo-1.1_1.aarch64.xbps', 1)
        self.write('obsolete', 'foo-1.0_1.aarch64.xbps\n')
        out = self.care('clean-cache')
        self.assertEqual(self.status, 0, out)
        self.assertEqual(out, 'Freed 3 MB from the package cache.\n')
        self.assertEqual(self.log('xbps.log'), ['remove -O'])       # never -OO, never -o
        self.assertEqual(sorted(p.name for p in self.cache.iterdir()), ['foo-1.1_1.aarch64.xbps'])

    def test_nothing_obsolete_prints_nothing(self):
        self.cached('foo-1.1_1.aarch64.xbps', 1)
        self.assertEqual(self.care('clean-cache'), '')
        self.assertEqual(self.status, 0)

    def test_orphans_are_named_not_removed(self):
        self.write('orphans', 'libold-2.0_1\npython3-foo-1.2_3\n')
        out = self.care('clean-cache')
        self.assertIn('No longer needed by anything: libold python3-foo', out)
        self.assertIn('cleanup', out)
        self.assertEqual(self.log('xbps.log'), ['remove -O'])


class AfterInstallTest(Stubbed):
    """The shell helpers and abyss-software clean the cache after a successful
    xbps-install only. A stub disk-care records the calls."""

    def setUp(self):
        super().setUp()
        self.marker = self.root / 'care.log'
        self.stub('care', f'echo "$*" >> "{self.marker}"; echo "Freed 2 MB from the package cache."')
        self.env['ABYSS_DISK_CARE'] = str(self.bin / 'care')

    def shell(self, code):
        return self.run_cmd(['bash', '--norc', '--noprofile', '-i', '-c', f'. "{PROFILE}"; {code}'],
                            env={'PS1': '$ '})

    def test_upgrade_ends_with_the_freed_space(self):
        out = self.shell('upgrade')
        self.assertEqual(self.status, 0, out)
        self.assertEqual(self.log('care.log'), ['clean-cache'])
        self.assertTrue(out.rstrip().endswith('System is up to date.\nFreed 2 MB from the package cache.'), out)

    def test_install_cleans_after_success(self):
        out = self.shell('install maim')
        self.assertEqual(self.status, 0, out)
        self.assertEqual(self.log('care.log'), ['clean-cache'])

    def test_failed_upgrade_or_install_leaves_the_cache(self):
        self.write('install-fail', '')
        self.shell('upgrade')
        self.assertEqual(self.status, 19)
        self.shell('install maim')
        self.assertEqual(self.status, 19)
        self.assertEqual(self.log('care.log'), [])

    def test_upgrade_with_the_real_helper(self):
        self.env['ABYSS_DISK_CARE'] = str(CARE)
        self.cached('foo-1.0_1.aarch64.xbps', 5)
        self.write('obsolete', 'foo-1.0_1.aarch64.xbps\n')
        out = self.shell('upgrade')
        self.assertEqual(self.status, 0, out)
        self.assertTrue(out.rstrip().endswith('Freed 5 MB from the package cache.'), out)

    def test_abyss_software_cleans_after_a_successful_install_only(self):
        out = self.run_cmd(['/bin/sh', str(SOFTWARE), '--run-install', '--yes', 'firefox'])
        self.assertEqual(self.status, 0, out)
        self.assertIn('Freed 2 MB from the package cache.', out)
        self.assertEqual(self.log('care.log'), ['clean-cache'])
        self.marker.unlink()
        self.write('install-fail', '')
        out = self.run_cmd(['/bin/sh', str(SOFTWARE), '--run-install', '--yes', 'gimp'])
        self.assertNotEqual(self.status, 0, out)
        self.assertEqual(self.log('care.log'), [])


class TrimServiceTest(Stubbed):
    def setUp(self):
        super().setUp()
        self.stamp = self.root / 'state/fstrim-last'
        self.trimlog = self.root / 'log/abyss-fstrim.log'
        sysblock = self.root / 'sys/block'
        for dev, maxb in (('vda', '2147450880'), ('loop0', '4294966784'), ('sr0', '0')):
            (sysblock / dev / 'queue').mkdir(parents=True)
            (sysblock / dev / 'queue/discard_max_bytes').write_text(maxb + '\n')
        self.write('cmdline', 'root=UUID=1234 ro quiet splash\n')
        self.stub('fstrim', 'echo "fstrim $*" >> "$HOME/fstrim.log"\n'
                            'echo "/boot/efi: 0 B (0 bytes) trimmed on /dev/vda1"\n'
                            'echo "/: 1.2 GiB (1288490188 bytes) trimmed on /dev/vda2"')
        self.env.update({'ABYSS_TRIM_STAMP': str(self.stamp), 'ABYSS_TRIM_LOG': str(self.trimlog),
                         'ABYSS_SYS_BLOCK': str(sysblock), 'ABYSS_CMDLINE': str(self.root / 'cmdline'),
                         'ABYSS_TRIM_DELAY': '0', 'ABYSS_TRIM_ONCE': '1'})

    def service(self):
        out = self.care('trim-service')
        self.assertEqual(self.status, 0, out)
        return out

    def last(self, epoch):
        self.stamp.parent.mkdir(parents=True, exist_ok=True)
        self.stamp.write_text(f'{int(epoch)}\n')

    def trims(self):
        return self.log('fstrim.log')

    def test_first_run_trims_logs_one_line_and_records_the_time(self):
        out = self.service()
        self.assertEqual(self.trims(), ['fstrim -av'])
        self.assertRegex(out, r'^\d{4}-\d\d-\d\d \d\d:\d\d fstrim: trimmed /boot/efi: 0 B, /: 1.2 GiB\n$')
        self.assertEqual(self.trimlog.read_text(), out)
        self.assertAlmostEqual(int(self.stamp.read_text()), time.time(), delta=60)

    def test_not_due_within_a_week(self):
        self.last(time.time() - 6 * DAY)
        self.assertEqual(self.service(), '')
        self.assertEqual(self.trims(), [])

    def test_due_after_a_week_even_if_the_machine_was_off(self):
        self.last(time.time() - 7 * DAY - 60)
        self.service()
        self.assertEqual(self.trims(), ['fstrim -av'])
        self.assertEqual(self.service(), '')                     # recorded: not again
        self.assertEqual(len(self.trims()), 1)

    def test_a_stamp_from_the_future_or_garbage_does_not_block_it_forever(self):
        for content in (str(int(time.time() + 400 * DAY)), 'garbage', ''):
            with self.subTest(content=content):
                self.stamp.parent.mkdir(parents=True, exist_ok=True)
                self.stamp.write_text(content)
                self.service()
                self.assertTrue(int(self.stamp.read_text()) <= time.time() + 60)
        self.assertEqual(len(self.trims()), 3)

    def test_a_clock_slightly_behind_the_stamp_waits(self):
        self.last(time.time() + 3600)                             # chrony stepped back an hour
        self.service()
        self.assertEqual(self.trims(), [])

    def test_live_iso_never_trims(self):
        self.write('cmdline', 'root=live:CDLABEL=VOID_LIVE ro init=/sbin/init\n')
        self.assertEqual(self.service(), '')
        self.assertEqual(self.trims(), [])
        self.assertFalse(self.stamp.exists())

    def test_no_discard_capable_disk_logs_and_waits_a_week(self):
        (self.root / 'sys/block/vda/queue/discard_max_bytes').write_text('0\n')
        out = self.service()
        self.assertIn('no disk here supports TRIM', out)
        self.assertEqual(self.trims(), [])
        self.assertTrue(self.stamp.exists())

    def test_a_failure_is_logged_and_retried_next_week(self):
        self.stub('fstrim', 'echo "fstrim: /: FITRIM ioctl failed: Operation not supported" >&2; exit 1')
        out = self.service()
        self.assertIn('fstrim: exit 1: fstrim: /: FITRIM ioctl failed', out)
        self.assertTrue(self.stamp.exists())

    def test_the_log_keeps_the_last_fifty_lines(self):
        self.trimlog.parent.mkdir(parents=True)
        self.trimlog.write_text(''.join(f'old {i}\n' for i in range(80)))
        self.service()
        lines = self.trimlog.read_text().splitlines()
        self.assertEqual(len(lines), 50)
        self.assertEqual(lines[0], 'old 31')
        self.assertIn('fstrim: trimmed', lines[-1])

    def test_runit_service_runs_the_scheduler(self):
        run = (Path(PKG) / 'files/abyss-fstrim/run').read_text()
        self.assertIn('exec 2>&1', run)
        self.assertIn('exec /usr/libexec/abyss-desktop/disk-care trim-service', run)
        self.assertTrue(os.access(Path(PKG) / 'files/abyss-fstrim/run', os.X_OK))


@unittest.skipUnless(CARE.is_file(), 'abyss-desktop not found; set ABYSS_DESKTOP_PKG')
class EnableOnceTest(unittest.TestCase):
    LINK = 'etc/runit/runsvdir/default/abyss-fstrim'
    STAMP = 'var/lib/abyss-desktop/fstrim-enabled'

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        (self.root / 'etc/runit/runsvdir/default').mkdir(parents=True)
        helper = self.root / 'usr/libexec/abyss-desktop/local-bin-wrappers'
        helper.parent.mkdir(parents=True)
        shutil.copy(Path(PKG) / 'files/local-bin-wrappers', helper)
        run = self.root / 'etc/sv/abyss-fstrim/run'        # unpacked by xbps before INSTALL post
        run.parent.mkdir(parents=True)
        shutil.copy(Path(PKG) / 'files/abyss-fstrim/run', run)
        self.scripts = {}
        for name in ('INSTALL', 'REMOVE'):
            script = self.root.parent / f'{self.root.name}.{name}'
            script.write_text(HEADER + (Path(PKG) / name).read_text() + '\nexit 0\n')
            self.addCleanup(script.unlink)
            self.scripts[name] = script

    def run_script(self, name, action='post', update='yes'):
        result = subprocess.run(['/bin/sh', str(self.scripts[name]), action, 'abyss-desktop', '1.0_38', update, 'no',
                                 'aarch64'], cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout)
        return result.stdout

    def path(self, rel):
        return self.root / rel

    def test_enabled_once(self):
        out = self.run_script('INSTALL')
        self.assertEqual(os.readlink(self.path(self.LINK)), '/etc/sv/abyss-fstrim')
        self.assertIn('enabled abyss-fstrim', out)
        self.assertTrue(self.path(self.STAMP).is_file())
        self.assertNotIn('abyss-fstrim', self.run_script('INSTALL'))       # the next update: quiet

    def test_user_removal_is_respected(self):
        self.run_script('INSTALL')
        self.path(self.LINK).unlink()                                       # rm /var/service/abyss-fstrim
        self.run_script('INSTALL')
        self.assertFalse(os.path.lexists(self.path(self.LINK)))

    def test_an_existing_link_is_kept_and_recorded(self):
        self.path(self.LINK).symlink_to('/etc/sv/my-trim')
        self.assertNotIn('abyss-fstrim', self.run_script('INSTALL'))
        self.assertEqual(os.readlink(self.path(self.LINK)), '/etc/sv/my-trim')
        self.assertTrue(self.path(self.STAMP).is_file())

    def test_removing_the_package_drops_the_link(self):
        self.run_script('INSTALL')
        self.run_script('REMOVE', update='yes')                             # an update keeps it
        self.assertTrue(os.path.lexists(self.path(self.LINK)))
        self.run_script('REMOVE', update='no')
        self.assertFalse(os.path.lexists(self.path(self.LINK)))

    def test_template_installs_the_helper_and_the_service(self):
        template = (Path(PKG) / 'template').read_text()
        self.assertIn('vinstall ${FILESDIR}/disk-care 755 usr/libexec/abyss-desktop', template)
        self.assertIn('vsv abyss-fstrim', template)


if __name__ == '__main__':
    unittest.main()
