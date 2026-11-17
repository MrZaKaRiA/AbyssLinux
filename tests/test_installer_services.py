"""void-installer: the services checklist, the EFI boot entry name and the
UTF-8 character set dialog runs under.

The functions are cut out of custom-overlay/usr/bin/void-installer and run
with bash against a fake target root in a temporary directory; `dialog`,
`chroot`, `mount` and friends are shell stubs.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / 'custom-overlay/usr/bin/void-installer'
OVERLAY_SV = ROOT / 'custom-overlay/etc/sv'
TEXT = INSTALLER.read_text(encoding='utf-8')


def function(name):
    m = re.search(r'^%s\(\) \{\n.*?^\}\n' % re.escape(name), TEXT, re.S | re.M)
    if not m:
        raise AssertionError('function %s not found in void-installer' % name)
    return m.group(0)


def assignment(name):
    m = re.search(r'^%s=.*$' % re.escape(name), TEXT, re.M)
    if not m:
        raise AssertionError('%s= not found in void-installer' % name)
    return m.group(0)


# Run scripts as Void's packages ship them (shortened), plus the overlay's own
SERVICES = {
    'dbus': 'exec 2>&1\nexec dbus-daemon --system --nofork --nopidfile\n',
    'NetworkManager': '#!/bin/sh\nexec NetworkManager -n > /dev/null 2>&1\n',
    'lightdm': '#!/bin/sh\nsv check dbus >/dev/null || exit 1\nexec lightdm\n',
    'sshd': '#!/bin/sh\nssh-keygen -A >/dev/null 2>&1\n[ -r conf ] && . ./conf\nexec /usr/bin/sshd -D $OPTS\n',
    'polkitd': '#!/bin/sh\nexec 2>&1\nexec /usr/lib/polkit-1/polkitd --no-debug\n',
    'elogind': '#!/bin/sh\nexec /usr/libexec/elogind/elogind\n',
    'agetty-tty1': '#!/bin/sh\nGETTY=agetty\nexec setsid ${GETTY} ${GETTY_ARGS} tty1 38400 linux\n',
    'agetty-ttyAMA0': '#!/bin/sh\nexec setsid agetty -L ttyAMA0 115200 vt100\n',
    'udevd': '#!/bin/sh\nexec udevd\n',
    'sulogin': '#!/bin/sh\nexec sulogin\n',
    'iptables': '#!/bin/sh\n[ ! -e /etc/iptables/iptables.rules ] && exit 0\niptables-restore -w 3 /etc/iptables/iptables.rules || exit 1\nexec chpst -b iptables pause\n',
    'uuidd': '#!/bin/sh\nexec chpst -u _uuidd:_uuidd -/ /var/empty uuidd -F -P\n',
    'tor': '#!/bin/sh\nexec chpst -u tor nice -n 5 tor --RunAsDaemon 0\n',
    'acpid': '#!/bin/sh\nexec env -i PATH=/usr/bin acpid -f\n',
    'norun': None,
}
INSTALLED = ['usr/bin/dbus-daemon', 'usr/bin/NetworkManager', 'usr/bin/lightdm',
             'usr/bin/sshd', 'usr/lib/polkit-1/polkitd', 'usr/libexec/elogind/elogind',
             'usr/bin/agetty', 'usr/bin/setsid', 'usr/bin/udevd', 'usr/bin/sulogin',
             'usr/bin/chpst', 'usr/bin/pause', 'usr/bin/uuidd', 'usr/bin/nice',
             'usr/bin/env']  # no ollama, no tor, no acpid
ENABLED = ['dbus', 'polkit', 'NetworkManager', 'lightdm', 'elogind', 'udevd',
           'agetty-tty1', 'ollama']

STUBS = r'''
DIALOG() {
    printf '%s\n' "$@" > "$DIALOG_ARGS"
    printf '%s' "$DIALOG_ANSWER" > "$ANSWER"
    return 0
}
'''


class FakeTarget(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='abyss-installer-test-'))
        self.addCleanup(shutil.rmtree, self.tmp)
        self.target = self.tmp / 'target'
        sv = self.target / 'etc/sv'
        sv.mkdir(parents=True)
        for name, run in SERVICES.items():
            (sv / name).mkdir()
            if run is not None:
                (sv / name / 'run').write_text(run)
        for name in ('polkit', 'ollama'):  # the overlay's own run scripts
            shutil.copytree(OVERLAY_SV / name, sv / name)
        for path in INSTALLED:
            p = self.target / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('#!/bin/sh\n')
            p.chmod(0o755)
        self.runsvdir = self.target / 'etc/runit/runsvdir/default'
        self.runsvdir.mkdir(parents=True)
        for name in ENABLED:
            os.symlink('/etc/sv/' + name, self.runsvdir / name)

    def bash(self, script, **env):
        prologue = '\n'.join([
            'TARGETDIR="$1"; ANSWER="$2"; TARGET_SERVICES="$3"; LOG=/dev/null',
            assignment('SV_IGNORE'),
            function('sv_daemon_installed'), function('list_services'),
            function('menu_services'), function('enable_service'),
            function('disable_service'), STUBS])
        full_env = {'PATH': os.environ['PATH'], 'LC_ALL': 'C',
                    'DIALOG_ARGS': str(self.tmp / 'dialog-args')}
        full_env.update(env)
        result = subprocess.run(
            ['bash', '-c', prologue + '\n' + script, 'test', str(self.target),
             str(self.tmp / 'answer'), str(self.tmp / 'target-services')],
            capture_output=True, text=True, env=full_env, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout


class ServiceChecklist(FakeTarget):
    def test_offered_services(self):
        offered = self.bash('list_services').split()
        self.assertEqual(offered, sorted(['NetworkManager', 'agetty-ttyAMA0', 'dbus',
                                          'iptables', 'lightdm', 'polkit', 'sshd', 'uuidd']))

    def test_hidden_services(self):
        offered = set(self.bash('list_services').split())
        # duplicate of the overlay's polkit (the one Abyss enables)
        self.assertNotIn('polkitd', offered)
        self.assertIn('polkit', offered)
        # D-Bus starts elogind; its runit service restart-loops
        self.assertNotIn('elogind', offered)
        # programs that are not installed
        self.assertNotIn('ollama', offered)
        self.assertNotIn('tor', offered)
        self.assertNotIn('acpid', offered)
        self.assertNotIn('norun', offered)
        # the existing getty/udevd/sulogin filter still applies
        for name in ('agetty-tty1', 'udevd', 'sulogin'):
            self.assertNotIn(name, offered)

    def test_ollama_shown_once_installed(self):
        p = self.target / 'usr/bin/ollama'
        p.write_text('#!/bin/sh\n')
        p.chmod(0o755)
        self.assertIn('ollama', self.bash('list_services').split())

    def test_checklist_and_changes(self):
        self.bash('menu_services', DIALOG_ANSWER='NetworkManager dbus lightdm polkit uuidd')
        args = (self.tmp / 'dialog-args').read_text().split('\n')
        items = args[args.index('18') + 1:]
        items = [i for i in items if i]
        triples = {items[i]: items[i + 2] for i in range(0, len(items), 3)}
        self.assertEqual(triples, {'NetworkManager': 'on', 'agetty-ttyAMA0': 'off', 'dbus': 'on',
                                   'iptables': 'off', 'lightdm': 'on', 'polkit': 'on',
                                   'sshd': 'off', 'uuidd': 'off'})
        enabled = sorted(p.name for p in self.runsvdir.iterdir())
        # uuidd ticked; hidden services keep their state, including ollama and elogind
        self.assertEqual(enabled, sorted(ENABLED + ['uuidd']))
        self.assertEqual(os.readlink(self.runsvdir / 'uuidd'), '/etc/sv/uuidd')

    def test_unticking_disables(self):
        self.bash('menu_services', DIALOG_ANSWER='dbus lightdm polkit')
        enabled = {p.name for p in self.runsvdir.iterdir()}
        self.assertNotIn('NetworkManager', enabled)
        self.assertTrue({'elogind', 'ollama', 'udevd', 'agetty-tty1'} <= enabled)


class BootloaderId(FakeTarget):
    def test_no_void_grub_left(self):
        code = [l for l in TEXT.splitlines() if not l.lstrip().startswith('#')]
        self.assertEqual([l for l in code if 'void_grub' in l], [])

    def test_one_id_everywhere(self):
        self.assertIn('\nEFI_BOOTLOADER_ID=Abyss\n', TEXT)
        body = function('set_bootloader')
        self.assertIn('--bootloader-id=$EFI_BOOTLOADER_ID', body)
        for path in re.findall(r'EFI/[^/"\s]+', body):
            self.assertIn(path, ('EFI/$EFI_BOOTLOADER_ID', 'EFI/BOOT'))
        # the --no-nvram --removable retry reuses the same arguments
        self.assertRegex(body, r'grub-install \$grub_args --no-nvram --removable')

    def run_set_bootloader(self, efi_target, grub_name, fallback, fail_first=False):
        stubs = r'''
get_option() { echo /dev/vda; }
modprobe() { :; }
mount() { :; }
mountpoint() { return 0; }
DIALOG() { echo "DIALOG $*" >&2; return 0; }
DIE() { echo "DIE $*" >&2; exit 1; }
chroot() {
    shift
    case "$1" in
    grub-install)
        local id= removable=0 a
        for a in "$@"; do
            case "$a" in --bootloader-id=*) id=${a#*=} ;; --removable) removable=1 ;; esac
        done
        if [ "$removable" = 1 ]; then
            mkdir -p "$TARGETDIR/boot/efi/EFI/BOOT"; : > "$TARGETDIR/boot/efi/EFI/BOOT/$FALLBACK"
        elif [ -n "$FAIL_FIRST" ]; then
            return 1
        else
            : > "$TARGETDIR/boot/efi/EFI/$id/$GRUB_NAME"
        fi ;;
    esac
    return 0
}
'''
        script = '\n'.join(['LOGFILE=/dev/null', 'EFI_SYSTEM=1', 'EFI_TARGET=%s' % efi_target,
                            assignment('EFI_BOOTLOADER_ID'), function('log_run'),
                            function('log_tail'), function('set_bootloader'), stubs,
                            'set_bootloader'])
        self.bash(script, GRUB_NAME=grub_name, FALLBACK=fallback,
                  FAIL_FIRST='1' if fail_first else '')
        return self.target / 'boot/efi/EFI'

    def test_efi_install_paths(self):
        for efi_target, grub, fallback in (('arm64-efi', 'grubaa64.efi', 'BOOTAA64.EFI'),
                                           ('x86_64-efi', 'grubx64.efi', 'BOOTX64.EFI'),
                                           ('i386-efi', 'grubia32.efi', 'BOOTIA32.EFI')):
            with self.subTest(efi_target):
                esp = self.run_set_bootloader(efi_target, grub, fallback)
                self.assertTrue((esp / 'Abyss' / grub).is_file())
                self.assertTrue((esp / 'BOOT' / fallback).is_file())
                self.assertFalse((esp / 'void_grub').exists())
                shutil.rmtree(self.target / 'boot')

    def test_removable_retry(self):
        esp = self.run_set_bootloader('arm64-efi', 'grubaa64.efi', 'BOOTAA64.EFI', fail_first=True)
        self.assertTrue((esp / 'BOOT/BOOTAA64.EFI').is_file())
        self.assertFalse((esp / 'void_grub').exists())


class DialogText(unittest.TestCase):
    def test_dialog_texts_are_ascii(self):
        # Only the ISO-639 language name table may contain non-ASCII text
        lines = [l for l in TEXT.splitlines()
                 if re.search(r'[^\x00-\x7f]', l) and not l.lstrip().startswith('#')]
        self.assertEqual([l.strip() for l in lines], ['nb)  echo "Norwegian Bokmål" ;;'])

    def utf8_ctype(self, **env):
        stub = r'''
locale() {
    case "${LC_ALL:-${LC_CTYPE:-$LANG}}" in
        *.UTF-8|*.utf8) echo UTF-8 ;;
        *) echo ANSI_X3.4-1968 ;;
    esac
}
'''
        script = stub + function('utf8_ctype') + \
            'utf8_ctype; echo "rc=$? LC_ALL=${LC_ALL-unset} LC_CTYPE=${LC_CTYPE-unset} LANG=${LANG-unset}"'
        result = subprocess.run(['bash', '-c', script], capture_output=True, text=True,
                                env=dict(PATH=os.environ['PATH'], **env), timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_empty_environment_gets_utf8(self):
        # what doas without keepenv hands over
        self.assertEqual(self.utf8_ctype(), 'rc=0 LC_ALL=unset LC_CTYPE=C.UTF-8 LANG=unset')

    def test_c_locale_overridden(self):
        self.assertEqual(self.utf8_ctype(LC_ALL='C', LANG='C'),
                         'rc=0 LC_ALL=unset LC_CTYPE=C.UTF-8 LANG=C')

    def test_utf8_locale_kept(self):
        self.assertEqual(self.utf8_ctype(LANG='en_US.UTF-8'),
                         'rc=0 LC_ALL=unset LC_CTYPE=unset LANG=en_US.UTF-8')


if __name__ == '__main__':
    unittest.main()
