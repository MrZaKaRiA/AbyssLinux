#!/usr/bin/env python3
"""The sidebar migration fixes narrow values once and preserves user choices."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
INIT = Path(os.environ.get('ABYSS_CHOOSER_INIT', ROOT / 'custom-overlay/usr/local/bin/abyss-file-chooser-init'))

class SidebarInitTest(unittest.TestCase):
    def test_migrate_once_without_overriding_wide_sidebar(self):
        with tempfile.TemporaryDirectory(prefix='abyss-chooser-') as tmp:
            root = Path(tmp)
            binpath = root / 'bin'
            binpath.mkdir()
            mock = binpath / 'gsettings'
            mock.write_text('''#!/bin/sh
case "$1:$2" in
  get:org.gtk.Settings.FileChooser) echo 262 ;;
  get:org.gtk.gtk4.Settings.FileChooser) echo 140 ;;
  set:*) echo "$2 $3 $4" >> "$TEST_LOG" ;;
esac
''')
            mock.chmod(0o755)
            log = root / 'log'
            env = dict(os.environ, HOME=tmp, XDG_CONFIG_HOME=str(root / 'config'),
                       PATH=f'{binpath}:/usr/bin:/bin', DBUS_SESSION_BUS_ADDRESS='test', TEST_LOG=str(log))
            subprocess.run([str(INIT)], env=env, check=True)
            subprocess.run([str(INIT)], env=env, check=True)
            self.assertEqual(log.read_text().splitlines(), ['org.gtk.gtk4.Settings.FileChooser sidebar-width 300'])

if __name__ == '__main__':
    unittest.main()
