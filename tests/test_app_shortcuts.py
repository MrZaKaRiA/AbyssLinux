#!/usr/bin/env python3
"""Exercise application shortcut dispatch with a minimal graphical-session PATH."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CENTER = Path(os.environ.get('ABYSS_CENTER', ROOT / 'custom-overlay/usr/local/bin/abyss-control-center'))

class AppShortcutTests(unittest.TestCase):
    def run_action(self, action, program_path):
        with tempfile.TemporaryDirectory(prefix='abyss-app-') as tmp:
            root = Path(tmp)
            home = root / 'home with spaces'
            bindir = root / 'bin'
            bindir.mkdir()
            app = home / program_path
            app.parent.mkdir(parents=True)
            app.write_text('#!/bin/sh\nprintf launched > "$ABYSS_TEST_LOG"\n')
            app.chmod(0o755)
            setsid = bindir / 'setsid'
            setsid.write_text('#!/bin/sh\n[ "$1" != -f ] || shift\nexec "$@"\n')
            setsid.chmod(0o755)
            log = root / 'launched'
            env = os.environ.copy()
            env.update(HOME=str(home), PATH=f'{bindir}:/usr/bin:/bin', ABYSS_TEST_LOG=str(log))
            subprocess.run([str(CENTER), action], env=env, check=True, timeout=10)
            self.assertEqual(log.read_text(), 'launched')

    def test_vscode_uses_user_installer_path_without_session_path(self):
        self.run_action('code', '.local/opt/vscode/code')

    def test_vscode_finds_user_local_bin(self):
        self.run_action('code', '.local/bin/code')

    def test_browser_finds_user_local_bin(self):
        self.run_action('browser', '.local/bin/firefox')

if __name__ == '__main__':
    unittest.main()
