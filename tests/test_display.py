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
