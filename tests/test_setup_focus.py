"""The setup menu (abyss-setup) and the terminals it opens: a terminal that
asks for the doas password must keep the keyboard. The setup menu waits for
it (Install software, Optional repositories, Enable a service) and comes
back once it is closed, instead of grabbing the keyboard over the password
prompt. abyss-software on its own (menu, control center, bar) still starts
its terminal detached and closes. The real abyss-setup and abyss-software
run with stub dmenu, st, setsid and xbps; no X."""
from pathlib import Path
import subprocess
import unittest

from test_software_packages import SETUP, SOFTWARE, StubbedTest

AUDIO = 'Audio support (PipeWire + mixer)'

# dmenu and st write to one event log, so the order shows whether the setup
# menu came back while the terminal was still open.
DMENU = r'''prompt=
while [ $# -gt 0 ]; do [ "$1" = -p ] && { prompt=$2; shift; }; shift; done
cat > /dev/null
echo "menu $prompt" >> "$HOME/events.log"
a="$HOME/dmenu.answers"
[ -s "$a" ] || exit 1
head -n 1 "$a"
tail -n +2 "$a" > "$a.new"; mv "$a.new" "$a"'''
ST = r'''title=; cmd=
while [ $# -gt 0 ]; do
    case $1 in -t) title=$2; shift ;; -e) shift; break ;; esac; shift
done
echo "terminal $title (wait=${ABYSS_SOFTWARE_WAIT-unset})" >> "$HOME/events.log"
printf '%s\n' "$*" >> "$HOME/terminal.log"
echo "closed $title" >> "$HOME/events.log"'''
SETSID = r'''[ "$1" = -f ] && shift
echo "detached $1" >> "$HOME/events.log"'''


@unittest.skipUnless(SETUP.is_file() and SOFTWARE.is_file(), 'set ABYSS_SETUP and ABYSS_SOFTWARE')
class SetupFocusTest(StubbedTest):
    def setUp(self):
        super().setUp()
        self.stub('dmenu', DMENU)
        self.stub('st', ST)
        self.stub('setsid', SETSID)
        # the CI container runs as root: abyss-priv would not ask, but the
        # terminal must be opened all the same
        self.stub('id', 'echo 1000')
        self.stub('abyss-software', f'exec /bin/sh {SOFTWARE} "$@"')
        self.stub('abyss-display', 'echo "display" >> "$HOME/events.log"')
        self.stub('abyss-keyboard', 'exit 0')
        self.sv = self.root / 'sv'

    def answers(self, *lines):
        self.write('dmenu.answers', ''.join(line + '\n' for line in lines))

    def setup_menu(self):
        result = subprocess.run(['/bin/sh', str(SETUP)], env=self.env, cwd=self.root,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout)
        return self.log('events.log')

    def test_install_terminal_is_waited_for_before_the_setup_menu_returns(self):
        self.answers('Install software', AUDIO)          # then Esc at the setup menu
        self.assertEqual(self.setup_menu(), [
            'menu Abyss setup',
            'menu Software (type to filter)',
            'terminal Install software (wait=unset)',   # not passed on to the install
            'closed Install software',
            'menu Abyss setup',                          # only once it was closed
        ])
        self.assertRegex(self.log('terminal.log')[0], r"--run-install pipewire wireplumber pavucontrol;")

    def test_software_alone_still_detaches_its_terminal_and_closes(self):
        self.answers(AUDIO)
        self.software()
        self.assertEqual(self.status, 0, self.output)
        self.assertEqual(self.log('events.log'), ['menu Software (type to filter)', 'detached st'])

    def test_wait_mode_is_not_passed_on_to_the_terminal(self):
        # A terminal opened by the install (or anything it starts) is a plain
        # abyss-software again: the variable is dropped once read.
        self.answers(AUDIO)
        self.software(env={'ABYSS_SOFTWARE_WAIT': '1'})
        self.assertEqual(self.log('events.log'), ['menu Software (type to filter)',
                                                  'terminal Install software (wait=unset)',
                                                  'closed Install software'])

    def test_optional_repository_terminal_is_waited_for(self):
        self.answers('Optional repositories', 'Enable nonfree repository')
        self.assertEqual(self.setup_menu(), [
            'menu Abyss setup',
            'menu Optional Void repositories',
            'terminal Enable nonfree repository (wait=unset)',
            'closed Enable nonfree repository',
            'menu Optional Void repositories',
            'menu Abyss setup',
        ])
        self.assertIn('abyss-priv xbps-install -S void-repo-nonfree', self.log('terminal.log')[0])

    def test_enable_a_service_asks_for_the_password_in_a_terminal(self):
        # doas cannot ask without a terminal: from the menu it failed silently
        sv = Path('/etc/sv')
        services = sorted(p.name for p in sv.iterdir() if p.is_dir()
                          and not (Path('/var/service') / p.name).exists()) if sv.is_dir() else []
        if not services:
            self.skipTest('no runit service directories here')
        self.answers('Enable a service', services[0])
        self.assertEqual(self.setup_menu(), [
            'menu Abyss setup',
            'menu Enable runit service',
            f'terminal Enable {services[0]} (wait=unset)',
            f'closed Enable {services[0]}',
            'menu Abyss setup',
        ])
        self.assertIn(f"abyss-priv ln -s '/etc/sv/{services[0]}' '/var/service/{services[0]}'",
                      self.log('terminal.log')[0])

    def test_enable_a_service_command(self):
        # the same check without /etc/sv: the command the terminal runs
        text = SETUP.read_text()
        self.assertIn('term "Enable $service" "abyss-priv ln -s \'/etc/sv/$service\' '
                      '\'/var/service/$service\'', text)
        self.assertNotIn('setsid', text)


if __name__ == '__main__':
    unittest.main()
