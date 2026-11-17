"""Check display mode, refresh-rate and primary-output choices without an X server."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(os.environ.get('ABYSS_DISPLAY', Path(__file__).resolve().parents[1] / 'custom-overlay/usr/local/bin/abyss-display'))

# 34-inch 3440x1440 monitor: 60 Hz is the preferred mode, 180 Hz is offered.
ULTRAWIDE = '''Screen 0: minimum 320 x 200, current 3440 x 1440, maximum 16384 x 16384
DP-1 connected primary 3440x1440+0+0 (normal left inverted right x axis y axis) 797mm x 334mm
   3440x1440     59.97*+ 180.00   165.00   144.00   120.00    99.98
   2560x1440    180.00    59.95
   2560x1080    180.00    60.00
   1920x1080    119.88    60.00    59.94    50.00
   1920x1080i    60.00    50.00    59.94
   1280x720      60.00    50.00    59.94
   640x480       60.00    59.94
HDMI-1 disconnected (normal left inverted right x axis y axis)
'''

LAPTOP_AND_ULTRAWIDE = '''Screen 0: minimum 320 x 200, current 5360 x 1440, maximum 16384 x 16384
eDP-1 connected primary 1920x1200+0+0 (normal left inverted right x axis y axis) 302mm x 189mm
   1920x1200     60.00*+
DP-1 connected 3440x1440+1920+0 (normal left inverted right x axis y axis) 797mm x 334mm
   3440x1440    180.00*   59.97 +
'''

VM = '''Screen 0: minimum 320 x 200, current 1920 x 1200, maximum 8192 x 8192
Virtual-1 connected primary 1920x1200+0+0 (normal left inverted right x axis y axis) 0mm x 0mm
   1920x1200     59.95*+
   1920x1080     60.00
'''

# The same VM after its window was made full screen on a 3440x1440 monitor:
# the preferred mode moved, the desktop is still at the old size.
VM_RESIZED = '''Screen 0: minimum 320 x 200, current 1920 x 1200, maximum 8192 x 8192
Virtual-1 connected primary 1920x1200+0+0 (normal left inverted right x axis y axis) 0mm x 0mm
   3440x1440     59.97 +
   1920x1200     59.95*
   1920x1080     60.00
'''

# ... and with 1920x1080 chosen by hand.
VM_FIXED = '''Screen 0: minimum 320 x 200, current 1920 x 1080, maximum 8192 x 8192
Virtual-1 connected primary 1920x1080+0+0 (normal left inverted right x axis y axis) 0mm x 0mm
   3440x1440     59.97 +
   1920x1200     59.95
   1920x1080     60.00*
'''

AUTO_RES = 'Automatic resolution (follow the display / VM window)'
PICK = 'Choose resolution and refresh rate together\nVirtual-1\nAll modes exposed by this display\n'

INTERLACED = '''Screen 0: minimum 320 x 200, current 1920 x 1080, maximum 16384 x 16384
HDMI-1 connected primary 1920x1080+0+0 (normal left inverted right x axis y axis) 1600mm x 900mm
   1920x1080     60.00 +  50.00
   1920x1080i    50.00*   60.00
'''

PROPS = '''Screen 0: minimum 320 x 200, current 3440 x 1440, maximum 16384 x 16384
HDMI-1 connected primary 1920x1080+0+0 (normal left inverted right x axis y axis) 531mm x 299mm
\tBroadcast RGB: Automatic
\t\tsupported: Automatic, Full, Limited 16:235
\tmax bpc: 12
   1920x1080     60.00*+
DP-1 connected 3440x1440+1920+0 (normal left inverted right x axis y axis) 797mm x 334mm
\tmax bpc: 10
   3440x1440     59.97*+
DP-2 disconnected (normal left inverted right x axis y axis)
\tBroadcast RGB: Automatic
'''

XRANDR = r'''case " $* " in
    *" --prop "*) printf '%s' "${TEST_PROPS:-}"; exit 0 ;;
    *" --query "*) printf '%s' "$TEST_XRANDR"; exit 0 ;;
esac
printf '%s\n' "$*" >> "$HOME/xrandr.log"
[ -n "${TEST_FAIL:-}" ] || exit 0
case "$*" in *"$TEST_FAIL"*) exit 1 ;; esac'''

# Answers come from $HOME/answers, one per menu; no answer left means Escape.
DMENU = r'''{ printf 'MENU %s\n' "$*"; cat; } >> "$HOME/dmenu.log"
[ -s "$HOME/answers" ] || exit 1
head -n 1 "$HOME/answers"
tail -n +2 "$HOME/answers" > "$HOME/answers.next"; mv "$HOME/answers.next" "$HOME/answers"'''


class DisplayTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.config = self.root / '.config/abyss'
        self.config.mkdir(parents=True)
        self.stub('xrandr', XRANDR)
        self.stub('dmenu', DMENU)
        self.stub('timeout', 'shift; exec "$@"')
        self.env = dict(os.environ, HOME=str(self.root), PATH=f'{self.bin}:/usr/bin:/bin', TEST_XRANDR=ULTRAWIDE)
        self.env.pop('XDG_RUNTIME_DIR', None)
        self.env.pop('ABYSS_DISPLAY_PICKER', None)

    def stub(self, name, body):
        path = self.bin / name
        path.write_text('#!/bin/sh\n' + body + '\n')
        path.chmod(0o755)

    def run_display(self, *args, **env):
        """Run the script; return the xrandr commands that would change something."""
        result = subprocess.run(['/bin/sh', str(SCRIPT), *args], env=dict(self.env, **env),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.output = result.stdout
        self.status = result.returncode
        log = self.root / 'xrandr.log'
        return log.read_text().splitlines() if log.exists() else []

    def test_auto_uses_the_highest_rate_of_the_preferred_mode(self):
        calls = self.run_display('--auto')
        self.assertEqual(calls, ['--output DP-1 --auto',
                                 '--output DP-1 --mode 3440x1440 --rate 180.00'])
        self.assertEqual(self.status, 0)

    def test_restore_without_a_profile_does_the_same(self):
        self.assertIn('--output DP-1 --mode 3440x1440 --rate 180.00', self.run_display('--restore'))

    def test_saved_rate_wins(self):
        (self.config / 'refresh-rates').write_text('DP-1 144.00\n')
        calls = self.run_display('--auto')
        self.assertEqual(calls, ['--output DP-1 --auto',
                                 '--output DP-1 --mode 3440x1440 --rate 144.00'])

    def test_saved_rate_of_another_output_does_not_count(self):
        (self.config / 'refresh-rates').write_text('DP-10 60.00\n')
        self.assertIn('--output DP-1 --mode 3440x1440 --rate 180.00', self.run_display('--auto'))

    def test_opt_out_keeps_the_preferred_rate(self):
        (self.config / 'refresh-auto').write_text('preferred\n')
        self.assertEqual(self.run_display('--auto'), ['--output DP-1 --auto'])

    def test_saved_rate_no_longer_offered_leaves_the_default(self):
        # The user did choose a rate, so nothing is guessed in its place.
        (self.config / 'refresh-rates').write_text('DP-1 240.00\n')
        self.assertEqual(self.run_display('--auto'), ['--output DP-1 --auto'])

    def test_refused_rate_goes_back_to_the_preferred_one(self):
        calls = self.run_display('--auto', TEST_FAIL='--rate 180.00')
        self.assertEqual(calls, ['--output DP-1 --auto',
                                 '--output DP-1 --mode 3440x1440 --rate 180.00',
                                 '--output DP-1 --mode 3440x1440 --rate 59.97'])
        self.assertEqual(self.status, 0)

    def test_saved_profile_wins(self):
        (self.config / 'monitors.sh').write_text('xrandr --output DP-1 --mode 3440x1440 --rate 59.97 --pos 0x0\n')
        calls = self.run_display('--restore')
        self.assertEqual(calls, ['--output DP-1 --mode 3440x1440 --rate 59.97 --pos 0x0'])

    def test_output_missing_from_the_profile_gets_the_best_mode(self):
        (self.config / 'monitors.sh').write_text('xrandr --output eDP-1 --mode 1920x1200 --rate 60.00 --pos 0x0\n')
        calls = self.run_display('--restore')
        self.assertEqual(calls[1:], ['--output DP-1 --auto',
                                     '--output DP-1 --mode 3440x1440 --rate 180.00'])

    def test_single_rate_virtual_display_is_only_resized(self):
        self.assertEqual(self.run_display('--auto', TEST_XRANDR=VM), ['--output Virtual-1 --auto'])

    def test_interlaced_mode_is_left_alone(self):
        self.assertEqual(self.run_display('--auto', TEST_XRANDR=INTERLACED), ['--output HDMI-1 --auto'])

    def test_largest_output_becomes_primary(self):
        calls = self.run_display('--auto', TEST_XRANDR=LAPTOP_AND_ULTRAWIDE)
        self.assertEqual(calls, ['--output eDP-1 --auto',
                                 '--output DP-1 --auto --right-of eDP-1',
                                 '--output DP-1 --primary'])

    def test_common_sizes_list_every_ultrawide_rate(self):
        (self.root / 'answers').write_text('Choose resolution and refresh rate together\nDP-1\nCommon sizes (supported by this display)\n')
        self.assertEqual(self.run_display(), [])
        menu = (self.root / 'dmenu.log').read_text()
        for rate in ('59.97', '99.98', '120.00', '144.00', '165.00', '180.00'):
            self.assertIn(f'3440x1440 @ {rate} Hz — Ultrawide QHD\n', menu)
        self.assertNotIn('1920x1080i', menu)
        self.assertFalse((self.root / '.cache/abyss-display.pid').exists())

    def test_rate_picker_names_what_automatic_means(self):
        self.run_display('--rate', 'DP-1')
        self.assertIn('Automatic (highest the display offers)\n', (self.root / 'dmenu.log').read_text())
        (self.config / 'refresh-auto').write_text('preferred\n')
        self.run_display('--rate', 'DP-1')
        self.assertIn('Automatic (display default)\n', (self.root / 'dmenu.log').read_text())

    def test_automatic_in_the_rate_picker_forgets_the_saved_rate(self):
        (self.config / 'refresh-rates').write_text('DP-1 59.97\n')
        (self.root / 'answers').write_text('Automatic (highest the display offers)\n')
        self.assertEqual(self.run_display('--rate', 'DP-1'), ['--output DP-1 --mode 3440x1440 --rate 180.00'])
        self.assertEqual((self.config / 'refresh-rates').read_text(), '')

    def saved(self, name):
        path = self.config / name
        return path.read_text() if path.exists() else None

    def test_rate_only_choice_does_not_pin_the_resolution(self):
        (self.root / 'answers').write_text('144.00 Hz\nKeep 144.00 Hz\n')
        self.assertEqual(self.run_display('--rate', 'DP-1'), ['--output DP-1 --mode 3440x1440 --rate 144.00'])
        self.assertEqual(self.saved('refresh-rates'), 'DP-1 144.00\n')
        self.assertIsNone(self.saved('monitors.sh'))
        self.assertIsNone(self.saved('fixed-resolution'))

    def test_rate_choice_keeps_a_saved_layout_automatic(self):
        layout = 'xrandr --output eDP-1 --auto --pos 0x0\nxrandr --output DP-1 --auto --pos 1920x0\n'
        (self.config / 'monitors.sh').write_text(layout)
        (self.root / 'answers').write_text('59.97 Hz\nKeep 59.97 Hz\n')
        self.run_display('--rate', 'DP-1', TEST_XRANDR=LAPTOP_AND_ULTRAWIDE)
        self.assertEqual(self.saved('refresh-rates'), 'DP-1 59.97\n')
        self.assertEqual(self.saved('monitors.sh'), layout)
        self.assertIsNone(self.saved('fixed-resolution'))

    def test_restore_follows_a_changed_preferred_mode(self):
        self.assertEqual(self.run_display('--restore', TEST_XRANDR=VM_RESIZED), ['--output Virtual-1 --auto'])
        self.run_display('--status', TEST_XRANDR=VM_RESIZED)
        self.assertEqual(self.output, 'Virtual-1 automatic 1920x1200\n')

    def test_saved_layout_without_a_fixed_mode_follows_too(self):
        (self.config / 'monitors.sh').write_text('xrandr --output eDP-1 --off\nxrandr --output DP-1 --auto --pos 0x0\n')
        calls = self.run_display('--restore', TEST_XRANDR=LAPTOP_AND_ULTRAWIDE)
        self.assertEqual(calls[:2], ['--output eDP-1 --off', '--output DP-1 --auto --pos 0x0'])
        self.assertFalse([c for c in calls if '--mode' in c])

    def test_turning_an_output_off_saves_positions_not_modes(self):
        (self.root / 'answers').write_text('Turn an output off\neDP-1\n')
        self.run_display(TEST_XRANDR=LAPTOP_AND_ULTRAWIDE)
        self.assertEqual(self.saved('monitors.sh'),
                         'xrandr --output eDP-1 --auto --pos 0x0\nxrandr --output DP-1 --auto --pos 1920x0\n')
        self.assertIsNone(self.saved('fixed-resolution'))

    def test_resolution_chosen_in_the_picker_is_fixed_and_survives(self):
        (self.root / 'answers').write_text(PICK + '1920x1080 @ 60.00 Hz — Full HD / 1080p\n')
        calls = self.run_display(TEST_XRANDR=VM_FIXED)
        self.assertEqual(calls, ['--output Virtual-1 --mode 1920x1080 --rate 60.00'])
        menu = (self.root / 'dmenu.log').read_text()
        self.assertIn('Virtual-1 resolution (now automatic)', menu)
        self.assertIn(AUTO_RES + '\n1920x1080 @ 60.00 Hz', menu)
        line = 'xrandr --output Virtual-1 --mode 1920x1080 --rate 60.00 --pos 0x0\n'
        self.assertEqual(self.saved('monitors.sh'), line)
        self.assertEqual(self.saved('fixed-resolution'), 'Virtual-1\n')
        (self.root / 'xrandr.log').unlink()
        # The window is resized again: the fixed mode stays.
        self.assertEqual(self.run_display('--restore', TEST_XRANDR=VM_FIXED), [line[7:-1]])
        self.run_display('--status', TEST_XRANDR=VM_FIXED)
        self.assertEqual(self.output, 'Virtual-1 fixed 1920x1080\n')

    def test_fixed_mode_the_display_stopped_offering_falls_back_to_automatic(self):
        (self.config / 'monitors.sh').write_text('xrandr --output Virtual-1 --mode 3440x1440 --rate 59.97 --pos 0x0\n')
        (self.config / 'fixed-resolution').write_text('Virtual-1\n')
        calls = self.run_display('--restore', TEST_XRANDR=VM, TEST_FAIL='--mode 3440x1440')
        self.assertEqual(calls, ['--output Virtual-1 --mode 3440x1440 --rate 59.97 --pos 0x0', '--output Virtual-1 --auto'])

    def test_automatic_resolution_clears_the_fixed_mode(self):
        (self.config / 'monitors.sh').write_text('xrandr --output Virtual-1 --mode 1920x1080 --rate 60.00 --pos 0x0\n')
        (self.config / 'fixed-resolution').write_text('Virtual-1\n')
        (self.config / 'refresh-rates').write_text('Virtual-1 60.00\n')
        (self.root / 'answers').write_text(PICK + AUTO_RES + '\n')
        self.assertEqual(self.run_display(TEST_XRANDR=VM_FIXED), ['--output Virtual-1 --auto'])
        self.assertIn('Virtual-1 resolution (now fixed 1920x1080)', (self.root / 'dmenu.log').read_text())
        self.assertIsNone(self.saved('monitors.sh'))
        self.assertIsNone(self.saved('fixed-resolution'))
        self.assertEqual(self.run_display('--restore', TEST_XRANDR=VM_RESIZED)[1:], ['--output Virtual-1 --auto'])

    def test_automatic_resolution_keeps_the_rest_of_a_layout(self):
        (self.config / 'monitors.sh').write_text('xrandr --output eDP-1 --mode 1920x1200 --rate 60.00 --pos 0x0\n'
                                                 'xrandr --output DP-1 --mode 3440x1440 --rate 180.00 --pos 1920x0\n')
        calls = self.run_display('--auto-resolution', 'DP-1', TEST_XRANDR=LAPTOP_AND_ULTRAWIDE)
        self.assertEqual(calls, ['--output DP-1 --auto'])
        self.assertEqual(self.saved('monitors.sh'), 'xrandr --output eDP-1 --mode 1920x1200 --rate 60.00 --pos 0x0\n'
                                                    'xrandr --output DP-1 --auto --pos 1920x0\n')
        self.assertEqual(self.saved('fixed-resolution'), 'eDP-1\n')

    def test_virtual_display_pinned_by_an_older_version_is_automatic_again(self):
        # 27.3.2 .. abyss-desktop 1.0_25 saved the mode of every output; in a
        # VM that froze the desktop at one window size.
        (self.config / 'monitors.sh').write_text('xrandr --output Virtual-1 --mode 3440x1440 --rate 59.97 --pos 0x0\n')
        (self.config / 'refresh-rates').write_text('Virtual-1 59.97\n')
        self.assertEqual(self.run_display('--restore', TEST_XRANDR=VM), ['--output Virtual-1 --auto --pos 0x0'])
        self.run_display('--status', TEST_XRANDR=VM)
        self.assertEqual(self.output, 'Virtual-1 automatic 1920x1200\n')

    def test_older_layout_on_real_hardware_keeps_its_modes(self):
        (self.config / 'monitors.sh').write_text('xrandr --output DP-1 --mode 2560x1440 --rate 59.95 --pos 0x0\n')
        self.run_display('--status')
        self.assertEqual(self.output, 'DP-1 fixed 2560x1440\n')

    def test_full_range_only_touches_outputs_that_have_the_switch(self):
        calls = self.run_display('--full-range', TEST_XRANDR=PROPS, TEST_PROPS=PROPS)
        self.assertEqual(calls, ['--output HDMI-1 --set Broadcast RGB Full'])
        self.assertTrue((self.config / 'full-range').exists())
        self.assertIn('--output HDMI-1 --set Broadcast RGB Full', self.run_display('--auto', TEST_XRANDR=PROPS, TEST_PROPS=PROPS))
        calls = self.run_display('--full-range', 'off', TEST_XRANDR=PROPS, TEST_PROPS=PROPS)
        self.assertEqual(calls[-1], '--output HDMI-1 --set Broadcast RGB Automatic')
        self.assertFalse((self.config / 'full-range').exists())

    def test_full_range_without_the_switch_changes_nothing(self):
        self.assertEqual(self.run_display('--full-range', TEST_PROPS=ULTRAWIDE), [])
        self.assertEqual(self.status, 1)
        self.assertFalse((self.config / 'full-range').exists())


if __name__ == '__main__':
    unittest.main()
