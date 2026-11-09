#!/usr/bin/env python3
"""Exercise shortcut editing and conflict handling with a simulated dwm."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

EDITOR = Path(os.environ.get("ABYSS_EDITOR", Path(__file__).resolve().parents[1] / "custom-overlay/usr/local/bin/abyss-shortcut-editor"))
SHORTCUT_LIST = Path(os.environ.get("ABYSS_SHORTCUT_LIST", Path(__file__).resolve().parents[1] / "custom-overlay/usr/local/bin/abyss-shortcuts"))

DMENU = r'''#!/usr/bin/env python3
import json, os, sys
p = os.environ['ABYSS_TEST_QUEUE']
with open(p) as f: queue = json.load(f)
choice = queue.pop(0)
with open(p, 'w') as f: json.dump(queue, f)
lines = sys.stdin.read().splitlines()
if choice == '@first': choice = lines[0] if lines else ''
else: choice = next((x for x in lines if choice in x), '')
print(choice)
'''
HELPER = r'''#!/usr/bin/env python3
import json, os, pathlib, sys
p = pathlib.Path(os.environ['XDG_CONFIG_HOME']) / 'abyss/shortcuts.conf'
args = sys.argv[1:]
if args == ['--capture']:
    capture_file = os.environ.get('ABYSS_TEST_CAPTURES')
    if capture_file:
        p = pathlib.Path(capture_file)
        queue = json.loads(p.read_text())
        value = queue.pop(0)
        p.write_text(json.dumps(queue))
    else:
        value = os.environ['ABYSS_TEST_CAPTURE']
    print(value.replace(' ', '\t'))
elif args == ['--probe'] or (args and args[0] == '--probe'):
    sys.exit(int(os.environ.get('ABYSS_TEST_PROBE', '0')))
elif args == ['--reload']:
    pass
elif args == ['--list']:
    records = [x.split('\t') for x in p.read_text().splitlines()] if p.exists() and not os.environ.get('ABYSS_TEST_REJECT') else []
    for original, label in [('Return', 'Open terminal'), ('b', 'Open browser')]:
        mod, key = '64', original
        for row in records:
            if len(row) == 5 and row[:3] == ['B', '64', original]: mod, key = row[3:5]
        print('\t'.join(['B', '64', original, mod, key, label]))
    for row in records:
        if row and row[0] == 'A': print('\t'.join(row))
else: sys.exit(2)
'''
ST = r'''#!/usr/bin/env python3
import os, sys
args = sys.argv[1:]
i = args.index('-e')
os.execvp(args[i+1], args[i+1:])
'''
APPS = "#!/bin/sh\nprintf 'Demo browser\\t%s\\n' 'exec:/usr/bin/true'\n"


class EditorTest(unittest.TestCase):
    def test_text_list_reads_the_running_bindings(self):
        with tempfile.TemporaryDirectory(prefix="abyss-shortcut-list-test-") as tmp:
            root = Path(tmp)
            bindir = root / "bin"
            bindir.mkdir()
            helper = bindir / "abyss-key-capture"
            helper.write_text(HELPER)
            helper.chmod(0o755)
            config = root / "config/abyss/shortcuts.conf"
            config.parent.mkdir(parents=True)
            config.write_text("B\t64\tReturn\t64\tF2\nA\tapp-1\t64\tF3\tDemo\texec:demo\n")
            env = os.environ.copy()
            env.update(PATH=f"{bindir}:/usr/bin:/bin", XDG_CONFIG_HOME=str(root / "config"))
            result = subprocess.run([str(SHORTCUT_LIST)], env=env, stdin=subprocess.DEVNULL, text=True, capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Super+F2", result.stdout)
            self.assertIn("Launch Demo", result.stdout)

    def run_editor(self, queue, capture="64 F2", probe="0", reject="", initial=""):
        with tempfile.TemporaryDirectory(prefix="abyss-editor-test-") as tmp:
            root = Path(tmp)
            bindir = root / "bin"
            bindir.mkdir()
            for name, contents in {"dmenu": DMENU, "st": ST, "abyss-key-capture": HELPER, "abyss-apps": APPS}.items():
                path = bindir / name
                path.write_text(contents)
                path.chmod(0o755)
            queue_file = root / "queue.json"
            queue_file.write_text(json.dumps(queue))
            if initial:
                (root / "config/abyss").mkdir(parents=True)
                (root / "config/abyss/shortcuts.conf").write_text(initial)
            env = os.environ.copy()
            env.update(PATH=f"{bindir}:/usr/bin:/bin", XDG_CONFIG_HOME=str(root / "config"),
                       ABYSS_TEST_QUEUE=str(queue_file), ABYSS_TEST_CAPTURE=capture if isinstance(capture, str) else '', ABYSS_TEST_PROBE=probe,
                       ABYSS_TEST_REJECT=reject)
            if isinstance(capture, list):
                captures_file = root / "captures.json"
                captures_file.write_text(json.dumps(capture))
                env['ABYSS_TEST_CAPTURES'] = str(captures_file)
            result = subprocess.run([str(EDITOR)], env=env, text=True, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(queue_file.read_text()), [])
            config = root / "config/abyss/shortcuts.conf"
            return config.read_text() if config.exists() else ""

    def test_changes_a_system_shortcut(self):
        config = self.run_editor(["System shortcuts", "Open terminal", "Change shortcut", "@first", "Done"])
        self.assertIn("B\t64\tReturn\t64\tF2\n", config)

    def test_rejects_a_shortcut_used_by_another_action(self):
        config = self.run_editor(["System shortcuts", "Open terminal", "Change shortcut", "@first", "Done"], "64 b")
        self.assertEqual(config, "")

    def test_adds_an_application_shortcut(self):
        config = self.run_editor(["Add application shortcut", "Demo browser", "@first", "Done"], "64 F3")
        self.assertIn("\t64\tF3\tDemo browser\texec:/usr/bin/true\n", config)

    def test_changes_an_application_shortcut(self):
        config = self.run_editor(["Add application shortcut", "Demo browser", "@first", "Application shortcuts",
                                  "Demo browser", "Change shortcut", "@first", "Done"], ["64 F3", "64 F4"])
        self.assertIn("\t64\tF4\tDemo browser\texec:/usr/bin/true\n", config)
        self.assertNotIn("\t64\tF3\t", config)

    def test_removes_an_application_shortcut(self):
        config = self.run_editor(["Add application shortcut", "Demo browser", "@first", "Application shortcuts",
                                  "Demo browser", "Remove shortcut", "@first", "Done"], "64 F3")
        self.assertEqual(config, "")

    def test_rejects_an_external_global_grab(self):
        config = self.run_editor(["System shortcuts", "Open terminal", "Change shortcut", "@first", "Done"], probe="3")
        self.assertEqual(config, "")

    def test_rejects_unmodified_typing_keys(self):
        config = self.run_editor(["System shortcuts", "Open terminal", "Change shortcut", "@first", "Done"], "0 a")
        self.assertEqual(config, "")

    def test_rolls_back_if_dwm_rejects_the_change(self):
        config = self.run_editor(["System shortcuts", "Open terminal", "Change shortcut", "@first", "Done"], reject="1")
        self.assertEqual(config, "")

    def test_restores_all_defaults(self):
        config = self.run_editor(["Add application shortcut", "Demo browser", "@first", "Restore all defaults",
                                  "Restore defaults", "@first", "Done"], "64 F3")
        self.assertEqual(config, "")

    def test_restore_defaults_keeps_changes_when_an_external_program_owns_a_default(self):
        initial = "B\t64\tReturn\t64\tF2\n"
        config = self.run_editor(["Restore all defaults", "Restore defaults", "@first", "Done"], probe="3", initial=initial)
        self.assertEqual(config, initial)

    def test_disables_and_restores_a_system_shortcut(self):
        config = self.run_editor(["System shortcuts", "Open terminal", "Disable shortcut", "@first",
                                  "System shortcuts", "Open terminal", "Restore default", "@first", "Done"])
        self.assertEqual(config, "")


if __name__ == "__main__":
    unittest.main()
