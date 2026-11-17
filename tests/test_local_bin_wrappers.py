#!/usr/bin/env python3
"""/usr/local/bin on an Abyss system: every command abyss-desktop ships in
/usr/bin has a wrapper there (the historical path dwm, LightDM, the session
file and the doas/sudo rules use), written by the package's helper
usr/libexec/abyss-desktop/local-bin-wrappers. INSTALL runs it on every
install and update, builder/abyss-postsetup.sh runs it on the ISO image, and
REMOVE takes the wrappers away again.

Checks the helper's command list against files/bin and the image overlay,
and runs INSTALL/REMOVE the way xbps does (see test_desktop_install_migration).
The package is AbyssLinuxPMR/srcpkgs/abyss-desktop: next to this checkout,
inside the PMR checkout itself, or ABYSS_DESKTOP_PKG.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PKG = Path(os.environ.get('ABYSS_DESKTOP_PKG') or next(
    (str(p) for p in (ROOT / 'srcpkgs/abyss-desktop', ROOT.parent / 'AbyssLinuxPMR/srcpkgs/abyss-desktop')
     if (p / 'files/local-bin-wrappers').is_file()), ROOT / 'srcpkgs/abyss-desktop'))
HELPER = PKG / 'files/local-bin-wrappers'
OVERLAY = ROOT / 'custom-overlay'
REL = 'usr/libexec/abyss-desktop/local-bin-wrappers'
MARK = 'managed by abyss-desktop'
# Commands abyss-desktop builds instead of copying from files/bin
BUILT = {'abyss-key-capture'}
# Overlay-only entries: the installer exists only on the live ISO
OVERLAY_ONLY = {'void-installer'}

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


def helper_list():
    out = subprocess.run(['sh', str(HELPER), '--list'], stdout=subprocess.PIPE, text=True, check=True).stdout
    return out.split()


def wrapper_text(cmd):
    return subprocess.run(['sh', str(HELPER), '--print', cmd], stdout=subprocess.PIPE, text=True, check=True).stdout


def packaged_paths():
    """Every path do_install() in the template puts in the package."""
    template = (PKG / 'template').read_text()
    paths = {f'/usr/bin/{p.name}' for p in (PKG / 'files/bin').iterdir() if p.is_file()}
    paths |= {f'/usr/bin/{c}' for c in BUILT}
    for src, dest, name in re.findall(r'vinstall \$\{FILESDIR\}/(\S+) \d+ (\S+)(?: (\S+))?', template):
        paths.add(f'/{dest}/{name or Path(src).name}')
    return paths


@unittest.skipUnless(HELPER.is_file(), 'abyss-desktop package not found; set ABYSS_DESKTOP_PKG')
class CommandListTest(unittest.TestCase):
    def test_list_is_every_packaged_command(self):
        shipped = {p.name for p in (PKG / 'files/bin').iterdir() if p.is_file()} | BUILT
        self.assertEqual(set(helper_list()), shipped)
        self.assertEqual(len(helper_list()), len(set(helper_list())))

    def test_install_and_remove_use_the_helper_not_their_own_list(self):
        install = (PKG / 'INSTALL').read_text()
        remove = (PKG / 'REMOVE').read_text()
        self.assertIn(f'sh {REL}', install)
        self.assertIn('vinstall ${FILESDIR}/local-bin-wrappers 755 usr/libexec/abyss-desktop',
                      (PKG / 'template').read_text())
        for script in (install, remove):
            self.assertNotRegex(script, r'for cmd in abyss-')      # no second, stale list
        self.assertIn(MARK, remove)

    def test_wrapper_text_is_unchanged(self):
        # byte-identical to what every earlier abyss-desktop wrote, so existing
        # wrappers stay as they are and the image matches updated systems
        self.assertEqual(wrapper_text('abyss-power'),
                         '#!/bin/sh\n# managed by abyss-desktop; keep the historical Abyss command path\n'
                         'exec /usr/bin/abyss-power "$@"\n')

    @unittest.skipUnless(OVERLAY.is_dir(), 'needs the AbyssLinux overlay')
    def test_overlay_local_bin_holds_only_copies_of_packaged_commands(self):
        listed = set(helper_list())
        for entry in sorted((OVERLAY / 'usr/local/bin').iterdir()):
            with self.subTest(entry.name):
                if entry.name in OVERLAY_ONLY:
                    self.assertTrue(entry.is_symlink())
                    continue
                self.assertIn(entry.name, listed, 'overlay-only command: package it or list it in OVERLAY_ONLY')
                self.assertEqual(entry.read_bytes(), (PKG / 'files/bin' / entry.name).read_bytes(),
                                 'overlay and package copies differ')

    @unittest.skipUnless(OVERLAY.is_dir(), 'needs the AbyssLinux overlay')
    def test_overlay_does_not_replace_packaged_files(self):
        clash = sorted(p for p in packaged_paths() if os.path.lexists(OVERLAY / p.lstrip('/')))
        self.assertEqual(clash, [], 'the image overlay would overwrite these abyss-desktop files')


@unittest.skipUnless(HELPER.is_file(), 'abyss-desktop package not found; set ABYSS_DESKTOP_PKG')
class ScriptTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.scripts = {}
        for name in ('INSTALL', 'REMOVE'):
            path = self.root.parent / f'{self.root.name}.{name}'
            path.write_text(HEADER + (PKG / name).read_text() + '\nexit 0\n')
            self.addCleanup(path.unlink)
            self.scripts[name] = path
        (self.root / 'usr/local/bin').mkdir(parents=True)
        self.unpack('old')

    def unpack(self, version):
        """Put the package files in place, as xbps unpacks them."""
        for cmd in helper_list():
            path = self.root / 'usr/bin' / cmd
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f'#!/bin/sh\necho {cmd} {version}\n')
        helper = self.root / REL
        helper.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(HELPER, helper)

    def run_script(self, name, action, update='yes'):
        result = subprocess.run(['/bin/sh', str(self.scripts[name]), action, 'abyss-desktop', '1.0_31', update, 'no',
                                 'aarch64'], cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout)
        return result.stdout

    def update(self):
        self.run_script('INSTALL', 'pre')
        self.unpack('new')
        self.run_script('INSTALL', 'post')

    def local(self, cmd):
        return self.root / 'usr/local/bin' / cmd

    def assert_wrappers(self):
        for cmd in helper_list():
            self.assertEqual(self.local(cmd).read_text(), wrapper_text(cmd), cmd)
            self.assertEqual(self.local(cmd).stat().st_mode & 0o777, 0o755, cmd)

    def test_fresh_install_writes_every_wrapper(self):
        self.run_script('INSTALL', 'post', update='no')
        self.assert_wrappers()
        self.assertEqual(sorted(p.name for p in self.root.glob('usr/local/bin/*')), sorted(helper_list()))

    def test_image_copies_become_wrappers_without_backups(self):
        # a 27.3.3 install: full copies identical to the installed package's files
        for cmd in helper_list():
            shutil.copy(self.root / 'usr/bin' / cmd, self.local(cmd))
        self.update()
        self.assert_wrappers()
        self.assertEqual(list(self.root.glob('usr/local/bin/*.abyss-backup')), [])
        self.assertFalse((self.root / 'var/lib/abyss-desktop/.local-bin-copies').exists())

    def test_edited_command_is_backed_up_and_restored_on_removal(self):
        self.local('abyss-display').write_text('#!/bin/sh\necho my own display tool\n')
        self.update()
        self.assert_wrappers()
        backups = list(self.root.glob('usr/local/bin/*.abyss-backup'))
        self.assertEqual([p.name for p in backups], ['abyss-display.abyss-backup'])
        self.update()                                         # a second update keeps the one backup
        self.assertEqual(self.local('abyss-display.abyss-backup').read_text(),
                         '#!/bin/sh\necho my own display tool\n')
        self.run_script('REMOVE', 'post', update='no')
        self.assertEqual(self.local('abyss-display').read_text(), '#!/bin/sh\necho my own display tool\n')
        self.assertEqual([p.name for p in self.root.glob('usr/local/bin/*')], ['abyss-display'])

    def test_removal_drops_every_wrapper_and_leaves_other_files(self):
        self.run_script('INSTALL', 'post', update='no')
        self.local('my-script').write_text('#!/bin/sh\n')
        self.local('void-installer').symlink_to('/usr/bin/void-installer')
        self.run_script('REMOVE', 'post', update='yes')       # an update keeps them
        self.assert_wrappers()
        self.run_script('REMOVE', 'post', update='no')
        self.assertEqual(sorted(p.name for p in self.root.glob('usr/local/bin/*')), ['my-script', 'void-installer'])

    def test_image_build_replaces_overlay_copies(self):
        # what builder/abyss-postsetup.sh does after mklive copied the overlay
        for cmd in helper_list():
            self.local(cmd).write_text('#!/bin/sh\necho overlay copy\n')
        subprocess.run(['sh', REL, '--no-backup'], cwd=self.root, check=True)
        self.assert_wrappers()
        self.assertEqual(list(self.root.glob('usr/local/bin/*.abyss-backup')), [])

    def test_postsetup_runs_the_package_helper(self):
        postsetup = (ROOT / 'builder/abyss-postsetup.sh')
        if not postsetup.is_file():
            self.skipTest('needs the AbyssLinux builder')
        text = postsetup.read_text()
        self.assertIn(f'wrappers={REL}', text)
        self.assertIn('sh "$wrappers" --no-backup', text)


if __name__ == '__main__':
    unittest.main()
