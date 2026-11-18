"""Settings › Display › Display scale: preview, then keep or revert.

The control center applies the scale through abyss-scale; a choice is only
saved in ~/.config/abyss/dpi after "Keep this scale". Scripts come from
custom-overlay (AbyssLinux) or srcpkgs/abyss-desktop (AbyssLinuxPMR), or from
ABYSS_CENTER / ABYSS_SCALE.
"""
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def script(name, env):
    if os.environ.get(env):
        return pathlib.Path(os.environ[env]).resolve()
    for d in (ROOT / 'custom-overlay/usr/local/bin', ROOT / 'srcpkgs/abyss-desktop/files/bin'):
        if (d / name).is_file():
            return d / name
    raise unittest.SkipTest(f'{name} not found')


SCRIPT = script('abyss-control-center', 'ABYSS_CENTER')
SCALE = script('abyss-scale', 'ABYSS_SCALE')


class TextSize(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        (self.root / 'bin').mkdir()
        (self.root / 'bin/abyss-scale').symlink_to(SCALE)
        (self.root / '.config/abyss').mkdir(parents=True)
        (self.root / '.config/abyss/dpi').write_text('192\n')
        self.stub('xrdb', '''if [ "$1" = -query ]; then echo 'Xft.dpi: 192'; else cat >> "$HOME/merges"; fi''')
        self.stub('xrandr', '''echo 'Virtual-1 connected primary 3440x1440+0+0 0mm x 0mm\'''')
        self.stub('timeout', 'shift; exec "$@"')
        self.stub('dmenu', 'cat >/dev/null; printf "%s\\n" "$*" >> "$HOME/prompts"; printf "%s\\n" "$TEST_ANSWER"')
        self.stub('notify-send', 'printf "%s\\n" "$*" >> "$HOME/notices"')
        self.stub('abyss-cursor', 'exit 0')
        self.env = dict(os.environ, HOME=str(self.root), PATH=str(self.root / 'bin') + os.pathsep + os.environ['PATH'],
                        DISPLAY=':test', ABYSS_SCALE_ROOT=str(self.root))

    def stub(self, name, script):
        path = self.root / 'bin' / name
        path.write_text('#!/bin/sh\n' + script + '\n')
        path.chmod(0o755)

    def run_action(self, answer, action='dpi-96'):
        subprocess.run([str(SCRIPT), action], env=dict(self.env, TEST_ANSWER=answer), check=True)
        return (self.root / 'merges').read_text()

    def test_revert_keeps_previous_preference(self):
        result = self.run_action('Revert to previous scale')
        self.assertIn('Xft.dpi: 96', result)
        self.assertIn('xmenu.height: 56', result.split('Xft.dpi: 192')[-1])
        self.assertTrue(result.rstrip().endswith(f'abyss.scale: {os.getuid()} 192'))
        self.assertEqual((self.root / '.config/abyss/dpi').read_text(), '192\n')

    def test_cancel_reverts(self):
        result = self.run_action('')
        self.assertIn('Xft.dpi: 192', result)
        self.assertEqual((self.root / '.config/abyss/dpi').read_text(), '192\n')

    def test_confirm_persists(self):
        result = self.run_action('Keep this scale')
        self.assertNotIn('Xft.dpi: 192', result)
        self.assertEqual((self.root / '.config/abyss/dpi').read_text(), '96\n')
        self.assertIn('Keep display scale 100%? Reverts in 20 seconds', (self.root / 'prompts').read_text())
        self.assertIn('Display scale: 100%', (self.root / 'notices').read_text())

    def test_new_steps(self):
        for action, dpi in (('dpi-120', '120'), ('dpi-168', '168')):
            self.run_action('Keep this scale', action)
            self.assertEqual((self.root / '.config/abyss/dpi').read_text(), dpi + '\n')

    def test_automatic_forgets_the_pin_and_uses_the_screen(self):
        # The 192 pinned by an older menu on an Apple VM; back to automatic
        # on the ultrawide is 100%.
        result = self.run_action('Keep this scale', 'dpi-auto')
        self.assertIn('Xft.dpi: 96', result)
        self.assertFalse((self.root / '.config/abyss/dpi').exists())
        self.assertIn('Display scale: automatic (now 100%)', (self.root / 'notices').read_text())


if __name__ == '__main__':
    unittest.main()
