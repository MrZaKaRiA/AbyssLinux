"""Display scale (abyss-scale and its callers) without an X server.

The rule table, the overrides, live re-scaling after a resolution change, the
login screen and the Display menu rows. xrandr, xrdb, notify-send and pgrep are
stubs; ABYSS_SCALE_ROOT points /sys and /etc into a temporary directory.
Scripts come from custom-overlay (AbyssLinux) or srcpkgs/abyss-desktop
(AbyssLinuxPMR), or from ABYSS_SCALE / ABYSS_CENTER / ABYSS_DISPLAY_SETUP /
ABYSS_DISPLAY.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


def script(name, env):
    if os.environ.get(env):
        return Path(os.environ[env]).resolve()
    for d in (ROOT / 'custom-overlay/usr/local/bin', ROOT / 'srcpkgs/abyss-desktop/files/bin'):
        if (d / name).is_file():
            return d / name
    raise unittest.SkipTest(f'{name} not found')


SCALE = script('abyss-scale', 'ABYSS_SCALE')
CENTER = script('abyss-control-center', 'ABYSS_CENTER')
SETUP = script('abyss-display-setup', 'ABYSS_DISPLAY_SETUP')
DISPLAY = script('abyss-display', 'ABYSS_DISPLAY')

APPLE_ULTRAWIDE = 'Virtual-1 connected primary 3440x1440+0+0 (normal left inverted right x axis y axis) 0mm x 0mm'
APPLE_MBP14 = 'Virtual-1 connected primary 3024x1964+0+0 (normal left inverted right x axis y axis) 0mm x 0mm'


class ScaleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / 'home'
        self.home.mkdir()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        (self.root / 'sys/class/dmi/id').mkdir(parents=True)
        # xrdb keeps a real resource database in a file: -query prints it,
        # -merge replaces the keys it is given.
        self.stub('xrdb', '''db="$TEST_STATE/xrdb"; touch "$db"
if [ "$1" = -query ]; then cat "$db"; exit 0; fi
new=$(cat); printf '%s\\n' "$new" >> "$TEST_STATE/merges"
printf '%s\\n' "$new" | awk -F: 'NR == FNR { if ($1 != "") seen[$1] = 1; print; next } !($1 in seen)' - "$db" > "$db.new"
mv "$db.new" "$db"''')
        self.stub('xrandr', '''cat "$TEST_STATE/xrandr" 2>/dev/null''')
        self.stub('notify-send', '''printf '%s' "$*" | tr '\\n' ' ' >> "$TEST_STATE/notices"; echo >> "$TEST_STATE/notices"''')
        self.stub('pgrep', '''[ -e "$TEST_STATE/dwm-running" ]''')
        self.stub('abyss-cursor', '''printf '%s\\n' "$1" >> "$TEST_STATE/cursor"''')
        # abyss-scale alone on PATH, as the callers find it on a system
        scale_dir = self.root / 'scale-bin'
        scale_dir.mkdir()
        (scale_dir / 'abyss-scale').symlink_to(SCALE)
        self.env = dict(os.environ, HOME=str(self.home), TEST_STATE=str(self.root),
                        ABYSS_SCALE_ROOT=str(self.root), DISPLAY=':test',
                        PATH=f'{self.bin}:{scale_dir}:/usr/bin:/bin')

    def stub(self, name, body):
        path = self.bin / name
        path.write_text('#!/bin/sh\n' + body + '\n')
        path.chmod(0o755)

    def machine(self, vendor='', xrandr='', pci=None, product=''):
        (self.root / 'sys/class/dmi/id/sys_vendor').write_text(vendor + '\n')
        (self.root / 'sys/class/dmi/id/product_name').write_text(product + '\n')
        if pci:
            dev = self.root / 'sys/bus/pci/devices/0000:00:01.0'
            dev.mkdir(parents=True, exist_ok=True)
            (dev / 'subsystem_vendor').write_text(pci + '\n')
        (self.root / 'xrandr').write_text(xrandr + '\n')

    def scale(self, *args, check=True):
        return subprocess.run(['/bin/sh', str(SCALE), *args], env=self.env, check=check,
                              capture_output=True, text=True).stdout.strip()

    def read(self, name):
        path = self.root / name
        return path.read_text() if path.exists() else ''

    def xft(self):
        for line in self.read('xrdb').splitlines():
            if line.startswith('Xft.dpi:'):
                return int(line.split()[1])
        return None

    # --- the automatic rule ---------------------------------------------------
    def test_rule_table(self):
        cases = [
            ('Apple VM, 34-inch ultrawide (macOS at 1x)', 'Apple Inc.', APPLE_ULTRAWIDE, 96),
            ('Apple VM, 14-inch MacBook Pro full screen', 'Apple Inc.', APPLE_MBP14, 192),
            ('Apple VM, 27-inch 1440p monitor', 'Apple Inc.',
             'Virtual-1 connected primary 2560x1440+0+0 0mm x 0mm', 96),
            ('Apple VM, default 1920x1200 window', 'Apple Inc.',
             'Virtual-1 connected primary 1920x1200+0+0 0mm x 0mm', 96),
            ('Apple VM, 16-inch MacBook Pro', 'Apple Inc.',
             'Virtual-1 connected primary 3456x2234+0+0 0mm x 0mm', 192),
            ('Apple VM, 5K display', 'Apple Inc.',
             'Virtual-1 connected primary 5120x2880+0+0 0mm x 0mm', 192),
            ('real 27-inch 4K', 'Dell Inc.',
             'DP-1 connected primary 3840x2160+0+0 (normal left inverted right x axis y axis) 597mm x 336mm', 144),
            ('real 24-inch 1080p', 'Dell Inc.',
             'HDMI-1 connected primary 1920x1080+0+0 (normal left inverted right x axis y axis) 531mm x 299mm', 96),
            ('real 27-inch 1440p', 'Dell Inc.',
             'DP-1 connected primary 2560x1440+0+0 (normal left inverted right x axis y axis) 597mm x 336mm', 96),
            ('15-inch 4K laptop', 'LENOVO',
             'eDP-1 connected primary 3840x2160+0+0 (normal left inverted right x axis y axis) 344mm x 194mm', 192),
            ('15.6-inch 1080p laptop', 'LENOVO',
             'eDP-1 connected primary 1920x1080+0+0 (normal left inverted right x axis y axis) 344mm x 194mm', 120),
            ('rotated 24-inch 4K', 'Dell Inc.',
             'DP-1 connected primary 2160x3840+0+0 left (normal left inverted right x axis y axis) 527mm x 296mm', 168),
            ('no physical size, not a VM, 4K', 'Dell Inc.',
             'DP-1 connected primary 3840x2160+0+0 (normal left inverted right x axis y axis) 0mm x 0mm', 144),
            ('impossible physical size (a TV) falls back to pixels', 'Dell Inc.',
             'HDMI-1 connected primary 3840x2160+0+0 (normal left inverted right x axis y axis) 160mm x 90mm', 144),
            ('QEMU VM: its made-up EDID size is ignored', 'QEMU',
             'Virtual-1 connected primary 1920x1080+0+0 (normal left inverted right x axis y axis) 260mm x 140mm', 96),
            ('QEMU VM at a Retina size: no evidence for 200%', 'QEMU',
             'Virtual-1 connected primary 3024x1964+0+0 0mm x 0mm', 96),
            ('no display', 'Dell Inc.', '', 96),
        ]
        for name, vendor, xrandr, want in cases:
            with self.subTest(name):
                self.machine(vendor, xrandr)
                self.assertEqual(self.scale('--auto'), str(want))

    def test_apple_vm_found_by_pci_subsystem_too(self):
        self.machine('', APPLE_MBP14, pci='0x106b')
        self.assertEqual(self.scale('--auto'), '192')
        self.assertIn('Mac virtual machine', self.scale('--explain'))

    def test_primary_output_decides(self):
        self.machine('Dell Inc.', '\n'.join([
            'eDP-1 connected 3840x2160+0+0 (normal) 344mm x 194mm',
            'HDMI-1 connected primary 1920x1080+3840+0 (normal) 531mm x 299mm']))
        self.assertEqual(self.scale('--auto'), '96')

    def test_largest_output_without_a_primary(self):
        self.machine('Dell Inc.', '\n'.join([
            'HDMI-1 connected 1920x1080+0+0 (normal) 531mm x 299mm',
            'DP-1 connected 3840x2160+1920+0 (normal) 597mm x 336mm',
            'DP-2 disconnected (normal)']))
        self.assertEqual(self.scale('--auto'), '144')

    # --- overrides --------------------------------------------------------------
    def test_user_then_system_then_automatic(self):
        self.machine('Apple Inc.', APPLE_ULTRAWIDE)
        self.assertEqual(self.scale(), '96')
        (self.root / 'etc/abyss').mkdir(parents=True)
        (self.root / 'etc/abyss/dpi').write_text('144\n')
        self.assertEqual(self.scale(), '144')
        self.assertEqual(self.scale('--explain'), '144 system /etc/abyss/dpi')
        (self.home / '.config/abyss').mkdir(parents=True)
        (self.home / '.config/abyss/dpi').write_text('192\n')  # pinned in the old menu
        self.assertEqual(self.scale(), '192')
        self.assertEqual(self.scale('--default'), '144')
        self.assertEqual(self.scale('--auto'), '96')

    def test_bad_override_is_ignored(self):
        self.machine('Apple Inc.', APPLE_ULTRAWIDE)
        (self.home / '.config/abyss').mkdir(parents=True)
        for bad in ('abc', '5000', '12', ''):
            (self.home / '.config/abyss/dpi').write_text(bad)
            self.assertEqual(self.scale(), '96', bad)

    def test_apply_sets_every_resource_and_the_pointer(self):
        self.machine('Apple Inc.', APPLE_MBP14)
        self.scale('--login')
        db = self.read('xrdb')
        self.assertIn('Xft.dpi: 192', db)
        self.assertIn('xmenu.width: 520', db)
        self.assertIn('xmenu.height: 56', db)
        self.assertIn(f'abyss.scale: {os.getuid()} 192', db)
        self.assertEqual(self.read('cursor').split(), ['192'])
        self.assertEqual(self.read('notices'), '')

    def test_apply_rejects_bad_values(self):
        self.machine('Apple Inc.', APPLE_MBP14)
        r = subprocess.run(['/bin/sh', str(SCALE), '--apply', '9999'], env=self.env, capture_output=True)
        self.assertEqual(r.returncode, 2)
        self.assertIsNone(self.xft())

    # --- live changes -------------------------------------------------------------
    def test_resolution_change_rescales_once_with_one_notice(self):
        self.machine('Apple Inc.', APPLE_MBP14)
        self.scale('--login')
        (self.root / 'dwm-running').touch()
        self.assertEqual(self.xft(), 192)
        # The VM window moves from the MacBook screen to the ultrawide.
        self.machine('Apple Inc.', APPLE_ULTRAWIDE)
        self.scale('--update')
        self.scale('--update')        # the next display event: nothing new
        self.assertEqual(self.xft(), 96)
        notices = self.read('notices').splitlines()
        self.assertEqual(len(notices), 1)
        self.assertIn('Display scale changed to 100%', notices[0])
        self.assertEqual(self.read('merges').count('Xft.dpi:'), 2)  # login + one change
        # The pointer is re-fitted on every change, scale or not.
        self.assertEqual(self.read('cursor').split(), ['192', '96', '96'])
        # And back.
        self.machine('Apple Inc.', APPLE_MBP14)
        self.scale('--update')
        self.assertEqual(self.xft(), 192)
        self.assertIn('Display scale changed to 200%', self.read('notices').splitlines()[-1])

    def test_notice_without_a_notification_daemon_uses_dmenu(self):
        # The default install has no notify-send: a short dmenu line instead.
        (self.bin / 'notify-send').unlink()
        self.stub('timeout', 'shift; exec "$@"')
        self.stub('dmenu', '''printf '%s | %s\\n' "$*" "$(cat)" >> "$TEST_STATE/dmenu"''')
        self.machine('Apple Inc.', APPLE_MBP14)
        self.scale('--login')
        (self.root / 'dwm-running').touch()
        self.machine('Apple Inc.', APPLE_ULTRAWIDE)
        self.scale('--update')
        for _ in range(50):
            if self.read('dmenu'):
                break
            time.sleep(0.1)
        self.assertIn('-p Display scale changed to 100% | Open apps: restart them to use it.', self.read('dmenu'))
        self.assertEqual(self.xft(), 96)

    def test_pinned_scale_does_not_follow_the_screen(self):
        (self.home / '.config/abyss').mkdir(parents=True)
        (self.home / '.config/abyss/dpi').write_text('192\n')
        self.machine('Apple Inc.', APPLE_MBP14)
        self.scale('--login')
        (self.root / 'dwm-running').touch()
        self.machine('Apple Inc.', APPLE_ULTRAWIDE)
        self.scale('--update')
        self.assertEqual(self.xft(), 192)
        self.assertEqual(self.read('notices'), '')

    def test_old_xinitrc_value_is_corrected_quietly_at_login(self):
        # A 27.3.4 ~/.xinitrc merged Xft.dpi 192 itself; abyss-display --restore
        # (fit_desktop) then runs --update before dwm starts.
        self.machine('Apple Inc.', APPLE_ULTRAWIDE)
        (self.root / 'xrdb').write_text('Xft.dpi:\t192\nxmenu.width:\t520\n')
        self.scale('--update')
        self.assertEqual(self.xft(), 96)
        self.assertIn('xmenu.width: 260', self.read('xrdb'))
        self.assertEqual(self.read('notices'), '')

    def test_no_notice_before_dwm_runs(self):
        self.machine('Apple Inc.', APPLE_MBP14)
        self.scale('--login')
        self.machine('Apple Inc.', APPLE_ULTRAWIDE)
        self.scale('--update')        # restore at login: dwm not started yet
        self.assertEqual(self.xft(), 96)
        self.assertEqual(self.read('notices'), '')

    def test_another_users_marker_is_not_ours(self):
        # LightDM's greeter ran on the same X server as root.
        self.machine('Apple Inc.', APPLE_ULTRAWIDE)
        (self.root / 'xrdb').write_text('Xft.dpi:\t192\nabyss.scale:\t99999 192\n')
        (self.root / 'dwm-running').touch()
        self.scale('--update')
        self.assertEqual(self.xft(), 96)
        self.assertEqual(self.read('notices'), '')

    def test_display_restore_calls_update(self):
        self.machine('Apple Inc.', APPLE_ULTRAWIDE)
        (self.root / 'xrdb').write_text('Xft.dpi:\t192\n')
        self.stub('xrandr', '''case "$*" in *--query*|'') cat "$TEST_STATE/xrandr" ;; *) : ;; esac''')
        subprocess.run(['/bin/sh', str(DISPLAY), '--auto'], env=self.env, check=True, capture_output=True)
        self.assertEqual(self.xft(), 96)

    # --- login screen ---------------------------------------------------------------
    def test_greeter_uses_system_setting_never_a_users_file(self):
        self.machine('Apple Inc.', APPLE_MBP14)
        (self.home / '.config/abyss').mkdir(parents=True)
        (self.home / '.config/abyss/dpi').write_text('96\n')
        subprocess.run(['/bin/sh', str(SETUP)], env=self.env, check=True)
        self.assertEqual(self.xft(), 192)
        (self.root / 'etc/abyss').mkdir(parents=True)
        (self.root / 'etc/abyss/dpi').write_text('120\n')
        subprocess.run(['/bin/sh', str(SETUP)], env=self.env, check=True)
        self.assertEqual(self.xft(), 120)

    def test_greeter_on_the_ultrawide(self):
        self.machine('Apple Inc.', APPLE_ULTRAWIDE)
        subprocess.run(['/bin/sh', str(SETUP)], env=self.env, check=True)
        self.assertEqual(self.xft(), 96)

    # --- Settings › Display -------------------------------------------------------
    def menu_rows(self):
        self.stub('xmenu', '''cat > "$TEST_STATE/menu"''')
        self.stub('abyss-keyboard', 'echo Swap')
        self.stub('abyss-display', 'exit 0')
        self.stub('xdotool', 'exit 1')
        subprocess.run([str(CENTER)], env=self.env, check=False, capture_output=True, timeout=30)
        return [l.strip('\t') for l in self.read('menu').splitlines() if 'Display scale' in l]

    def test_menu_shows_automatic_and_choices(self):
        self.machine('Apple Inc.', APPLE_ULTRAWIDE)
        rows = self.menu_rows()
        self.assertEqual(len(rows), 6)
        self.assertRegex(rows[0], r'Display scale: automatic \(now 100%\)  ✓\tdpi-auto$')
        self.assertEqual([r.split('\t')[1] for r in rows],
                         ['dpi-auto', 'dpi-96', 'dpi-120', 'dpi-144', 'dpi-168', 'dpi-192'])
        self.assertIn('Display scale: 125%\tdpi-120', rows[2])
        self.assertFalse(any('Text size' in l for l in self.read('menu').splitlines()))

    def test_menu_marks_a_pinned_scale(self):
        self.machine('Apple Inc.', APPLE_MBP14)
        (self.home / '.config/abyss').mkdir(parents=True)
        (self.home / '.config/abyss/dpi').write_text('144\n')
        rows = self.menu_rows()
        self.assertRegex(rows[0], r'automatic \(now 200%\)\tdpi-auto$')
        self.assertIn('Display scale: 150%  ✓\tdpi-144', rows[3])


if __name__ == '__main__':
    unittest.main()
