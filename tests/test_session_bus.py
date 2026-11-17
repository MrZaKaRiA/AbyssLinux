"""Verify existing user sessions inherit the bus created by abyss-session."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SESSION = Path(__file__).resolve().parents[1] / 'custom-overlay/usr/local/bin/abyss-session'


class SessionBusTest(unittest.TestCase):
    def test_existing_xinitrc_inherits_new_bus(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bindir = root / 'bin'
            bindir.mkdir()
            bus = bindir / 'dbus-run-session'
            bus.write_text('#!/bin/sh\nexport DBUS_SESSION_BUS_ADDRESS=test-bus\nexec "$@"\n')
            bus.chmod(0o755)
            (root / '.xinitrc').write_text('printf "%s\\n" "$DBUS_SESSION_BUS_ADDRESS"\n')
            env = os.environ.copy()
            env.pop('DBUS_SESSION_BUS_ADDRESS', None)
            env.pop('ABYSS_DBUS_STARTED', None)
            env.update(HOME=temp, PATH=f'{bindir}:/usr/bin:/bin')
            result = subprocess.run(['/bin/sh', str(SESSION)], env=env, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), 'test-bus')

    def test_session_starts_locker_with_sleep_inhibitor_handoff(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bindir = root / 'bin'
            bindir.mkdir()
            for name, content in {
                'xss-lock': 'printf "%s\\n" "$@" > "$HOME/locker-args"',
                'slock': 'exit 0',
                'pgrep': 'exit 1',
            }.items():
                path = bindir / name
                path.write_text('#!/bin/sh\n' + content + '\n')
                path.chmod(0o755)
            (root / '.xinitrc').write_text('sleep 0.2\n')
            env = os.environ.copy()
            env.update(HOME=temp, PATH=f'{bindir}:/usr/bin:/bin', DBUS_SESSION_BUS_ADDRESS='test-bus')
            env.pop('ABYSS_LOCK_LISTENER_STARTED', None)
            result = subprocess.run(['/bin/sh', str(SESSION)], env=env, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / 'locker-args').read_text().splitlines(), ['--transfer-sleep-lock', '--', 'slock'])
