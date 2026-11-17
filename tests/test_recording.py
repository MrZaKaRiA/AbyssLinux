"""Exercise screen geometry and output handling without starting a recorder."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

RECORD = Path(__file__).resolve().parents[1] / 'custom-overlay/usr/local/bin/abyss-record'


class RecordingTest(unittest.TestCase):
    def test_records_screen_geometry_with_safe_arguments(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bindir = root / 'bin'
            bindir.mkdir()
            for name, content in {
                'xrandr': 'printf "Screen 0: minimum 8 x 8, current 1920 x 1080, maximum 32767 x 32767\\n"',
                'ffmpeg': 'printf "%s\\n" "$@" > "$TEST_ARGS"',
                'xdg-user-dir': 'printf "%s\\n" "$HOME/Videos"',
            }.items():
                path = bindir / name
                path.write_text('#!/bin/sh\n' + content + '\n')
                path.chmod(0o755)
            env = os.environ.copy()
            env.update(HOME=temp, PATH=f'{bindir}:/usr/bin:/bin', DISPLAY=':0', TEST_ARGS=str(root / 'args'))
            result = subprocess.run(['/bin/sh', str(RECORD)], env=env, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            args = (root / 'args').read_text().splitlines()
            self.assertIn('1920x1080', args)
            self.assertIn(':0+0,0', args)
            self.assertTrue(args[-1].startswith(str(root / 'Videos') + '/'))
