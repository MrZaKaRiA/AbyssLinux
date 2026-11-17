"""Check cursor scaling and user overrides without requiring an X server."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(os.environ.get('ABYSS_CURSOR', Path(__file__).resolve().parents[1] / 'custom-overlay/usr/local/bin/abyss-cursor'))


class CursorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.stub('xrdb', '''if [ "$1" = -query ]; then printf '%s\\n' "${TEST_RESOURCES:-}"; else cat >> "$HOME/resources"; fi''')
        self.stub('xrandr', '''printf '%s\\n' "${TEST_XRANDR:-DP-1 connected primary 3840x2160+0+0}"''')
        self.stub('xsetroot', '''printf '%s\\n' "$XCURSOR_SIZE" > "$HOME/root-size"''')
        self.env = dict(os.environ, HOME=str(self.root), PATH=f'{self.bin}:/usr/bin:/bin')
        self.env.pop('XCURSOR_SIZE', None)

    def stub(self, name, body):
        path = self.bin / name
        path.write_text('#!/bin/sh\n' + body + '\n')
        path.chmod(0o755)

    def run_cursor(self, *args, **env):
        subprocess.run(['/bin/sh', str(SCRIPT), *args], env=dict(self.env, **env), check=True)
        return (self.root / 'resources').read_text()

    def test_automatic_high_resolution(self):
        resources = self.run_cursor()
        self.assertIn('Xcursor.size: 48', resources)
        self.assertIn('Xcursor.theme: Adwaita', resources)
        self.assertEqual((self.root / 'root-size').read_text().strip(), '48')

    def test_saved_dpi_and_existing_theme(self):
        config = self.root / '.config/abyss/dpi'
        config.parent.mkdir(parents=True)
        config.write_text('144\n')
        resources = self.run_cursor(TEST_RESOURCES='Xcursor.theme: Custom', TEST_XRANDR='DP-1 connected primary 2560x1440+0+0')
        self.assertIn('Xcursor.size: 32', resources)
        self.assertNotIn('Xcursor.theme:', resources)

    def test_explicit_size_and_bad_dpi(self):
        self.assertIn('Xcursor.size: 40', self.run_cursor('bad', XCURSOR_SIZE='40'))

    def test_normal_resolution_gets_the_standard_size(self):
        self.assertIn('Xcursor.size: 24', self.run_cursor('96', TEST_XRANDR='DP-1 connected primary 1920x1080+0+0'))

    def test_pointer_is_never_smaller_than_the_standard_size(self):
        # Small screen and the smallest text scale: still not the legacy tiny pointer.
        resources = self.run_cursor('72', TEST_XRANDR='VGA-1 connected 1024x768+0+0')
        size = int(resources.split('Xcursor.size:')[1].split()[0])
        self.assertGreaterEqual(size, 24)

    def test_apple_vm_at_double_text_scale(self):
        # Reported case: 1920x1200 at 192 DPI got 64 px, far too big.
        vm = 'Virtual-1 connected primary 1920x1200+0+0 (normal left inverted right x axis y axis) 0mm x 0mm'
        self.assertIn('Xcursor.size: 48', self.run_cursor('192', TEST_XRANDR=vm))

    def test_pointer_follows_the_screen_not_only_the_text_size(self):
        # 4K at 100% text: the text scale alone gives 24 px, too small on that panel.
        self.assertIn('Xcursor.size: 48', self.run_cursor('96'))

    def test_physical_size_is_used_when_believable(self):
        # 27-inch 4K is 163 DPI: 32 px. A 24-inch 1080p panel is 92 DPI: 24 px.
        big = 'DP-1 connected primary 3840x2160+0+0 (normal left inverted right x axis y axis) 597mm x 336mm'
        self.assertIn('Xcursor.size: 32', self.run_cursor('96', TEST_XRANDR=big))
        (self.root / 'resources').unlink()
        small = 'HDMI-1 connected 1920x1080+0+0 (normal left inverted right x axis y axis) 531mm x 299mm'
        self.assertIn('Xcursor.size: 24', self.run_cursor('96', TEST_XRANDR=small))

    def test_bogus_physical_size_falls_back_to_pixels(self):
        tv = 'HDMI-1 connected 3840x2160+0+0 (normal left inverted right x axis y axis) 160mm x 90mm'
        self.assertIn('Xcursor.size: 48', self.run_cursor('96', TEST_XRANDR=tv))

    def test_saved_pointer_size_wins(self):
        config = self.root / '.config/abyss/cursor-size'
        config.parent.mkdir(parents=True)
        config.write_text('96\n')
        self.assertIn('Xcursor.size: 96', self.run_cursor(XCURSOR_SIZE='40'))


if __name__ == '__main__':
    unittest.main()
