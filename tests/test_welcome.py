"""The "Welcome to Abyss Linux" prompt (abyss-setup --first-run, started by
~/.xinitrc at every login): Start setup and Do not show again end it, Later
and Esc put it off, and it is put off at two logins at most. Opening setup
from the menu ends it too. dmenu is a stub; runs without X."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def first(*paths):
    return next((Path(p) for p in paths if p and Path(p).is_file()), None)


SETUP = first(os.environ.get('ABYSS_SETUP'), ROOT / 'custom-overlay/usr/local/bin/abyss-setup',
              ROOT / 'srcpkgs/abyss-desktop/files/bin/abyss-setup')

# Answers from $HOME/answers, one per prompt; none left is Esc (status 1).
DMENU = r'''
prompt=
while [ $# -gt 0 ]; do [ "$1" = -p ] && { prompt=$2; shift; }; shift; done
echo "$prompt" >> "$HOME/prompts.log"
cat > /dev/null
[ -s "$HOME/answers" ] || exit 1
head -n 1 "$HOME/answers"
sed 1d "$HOME/answers" > "$HOME/answers.new"; mv "$HOME/answers.new" "$HOME/answers"
'''

TOOLS = 'sh cat head sed mv mkdir rm'.split()


@unittest.skipUnless(SETUP, 'abyss-setup not found; set ABYSS_SETUP')
class WelcomeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve()
        self.bin = self.home / 'bin'
        self.bin.mkdir()
        for tool in TOOLS:
            found = shutil.which(tool, path='/usr/bin:/bin')
            if found:
                (self.bin / tool).symlink_to(found)
        self.stub('dmenu', DMENU)
        # what the setup menu could start: never the real ones
        for name in ('abyss-software', 'abyss-display', 'abyss-keyboard', 'abyss-priv', 'notify-send',
                     'setsid', 'st'):
            self.stub(name, f'echo "{name} $*" >> "$HOME/calls.log"')
        self.stub('sleep', 'exit 0')
        self.done = self.home / '.config/abyss/.first-run-done'

    def stub(self, name, body):
        path = self.bin / name
        if path.is_symlink():
            path.unlink()
        path.write_text('#!/bin/sh\n' + body + '\n')
        path.chmod(0o755)

    def login(self, *answers):
        """One login: the prompt, answered with ANSWERS (none: Esc). Returns
        the prompts shown."""
        (self.home / 'answers').write_text(''.join(a + '\n' for a in answers))
        (self.home / 'prompts.log').unlink(missing_ok=True)
        self.run_setup('--first-run')
        path = self.home / 'prompts.log'
        return path.read_text().splitlines() if path.exists() else []

    def run_setup(self, *args):
        # /usr/local/bin last: abyss-setup must not put it before the stubs
        env = {'HOME': str(self.home), 'PATH': f'{self.bin}:{self.home}/.local/bin:/usr/local/bin',
               'ABYSS_FIRST_RUN_DELAY': '0'}
        result = subprocess.run(['/bin/sh', str(SETUP), *args], env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_esc_counts_as_later_and_the_prompt_comes_back_once(self):
        self.assertEqual(self.login(), ['Welcome to Abyss Linux'])          # Esc
        self.assertFalse(self.done.exists())
        self.assertEqual(self.login(), ['Welcome to Abyss Linux'])          # the reminder, Esc
        self.assertTrue(self.done.exists())
        self.assertEqual(self.login(), [])
        self.assertEqual(self.login(), [])

    def test_later_twice_ends_it(self):
        self.assertEqual(self.login('Later'), ['Welcome to Abyss Linux'])
        self.assertEqual(self.login(), ['Welcome to Abyss Linux'])          # Later, then Esc
        self.assertEqual(self.login('Later'), [])

    def test_do_not_show_again(self):
        self.assertEqual(self.login('Do not show again'), ['Welcome to Abyss Linux'])
        self.assertTrue(self.done.exists())
        self.assertEqual(self.login(), [])

    def test_start_setup_ends_it_however_setup_is_left(self):
        # setup opens; Esc closes it
        self.assertEqual(self.login('Start setup'), ['Welcome to Abyss Linux', 'Abyss setup'])
        self.assertEqual(self.login(), [])

    def test_later_then_setup_from_the_menu_ends_it(self):
        self.login('Later')
        (self.home / 'answers').write_text('')
        self.run_setup()                       # Control center → setup
        self.assertEqual(self.login(), [])

    def test_a_garbled_count_is_a_fresh_start(self):
        count = self.home / '.config/abyss/.first-run-later'
        count.parent.mkdir(parents=True)
        count.write_text('x\n')
        self.assertEqual(self.login(), ['Welcome to Abyss Linux'])
        self.assertEqual(count.read_text(), '1\n')

    def test_nothing_else_is_started(self):
        self.login()
        self.login()
        self.assertFalse((self.home / 'calls.log').exists())


if __name__ == '__main__':
    unittest.main()
