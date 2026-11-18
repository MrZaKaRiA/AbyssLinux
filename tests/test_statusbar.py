"""The status bar: dwm-statusbar's modules (network, keyboard layout, Docker,
passwords, clock) and their click blocks, and abyss-bar's action for each
block and button. Runs without X: nmcli, xset, setxkbmap, docker, wpctl,
xmenu, dmenu, ... are stubs; /sys and /proc are small trees in a temporary
directory. dwm-statusbar needs bash 5 (EPOCHREALTIME); those tests are
skipped where there is none (macOS ships bash 3.2)."""
import calendar
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / 'custom-overlay/usr/local/bin'
STATUSBAR = Path(os.environ.get('ABYSS_STATUSBAR', BIN / 'dwm-statusbar')).resolve()
BAR = Path(os.environ.get('ABYSS_BAR', BIN / 'abyss-bar')).resolve()
# The dwm sources: the Abyss overlay tree, or the PMR package's patch.
DWM_C = ROOT / 'dwm/dwm.c'
DWM_PATCH = ROOT / 'srcpkgs/abyss-dwm/patches/40-statuscmd.patch'

# 2026-11-18 19:11:30 UTC, a Wednesday
NOW = calendar.timegm((2026, 11, 18, 19, 11, 30))
SYSTEM_PATH = '/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin'  # abyss-bar adds /usr/local/bin when it is missing


def find_bash5():
    for cand in (os.environ.get('ABYSS_BASH'), shutil.which('bash'), '/opt/homebrew/bin/bash',
                 '/usr/local/bin/bash', '/bin/bash', '/usr/bin/bash'):
        if not cand or not os.path.exists(cand):
            continue
        out = subprocess.run([cand, '-c', 'echo ${BASH_VERSINFO[0]}'], stdout=subprocess.PIPE, text=True)
        if out.stdout.strip().isdigit() and int(out.stdout) >= 5:
            return cand
    return None


BASH5 = find_bash5()


def write(path, text, mode=0o644):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(mode)


def stub(directory, name, body):
    write(Path(directory) / name, '#!/bin/sh\n' + body + '\n', 0o755)


class Sandbox:
    """A HOME with stub commands in $HOME/bin; files in HOME steer the stubs."""

    def __init__(self):
        # /tmp keeps the Docker socket path under the 104-byte limit (macOS)
        self.home = Path(tempfile.mkdtemp(prefix='abyss-bar-', dir='/tmp'))
        self.bin = self.home / 'bin'
        self.bin.mkdir()
        log = 'printf "%s %s\\n" "${0##*/}" "$*" >> "$HOME/calls.log"'
        stub(self.bin, 'nmcli', log + '''
case "$*" in
    *"radio wifi"*off*|*"radio wifi"*on*) exit 0 ;;
    *"radio wifi"*) cat "$HOME/radio" 2>/dev/null || echo enabled; exit 0 ;;
    *"-f TYPE device"*) sed 's/^[^:]*:\\([^:]*\\):.*/\\1/' "$HOME/nmcli.dev" 2>/dev/null; exit 0 ;;
    *"device wifi list"*) cat "$HOME/nmcli.wifi" 2>/dev/null; exit 0 ;;
    *device*) [ -e "$HOME/nm-down" ] && { echo 'Error: NetworkManager is not running.' >&2; exit 8; }
              cat "$HOME/nmcli.dev" 2>/dev/null ;;
esac''')
        stub(self.bin, 'xset', 'printf "  00: Caps Lock:   off    01: Num Lock:    off\\n'
                               '  auto repeat:  on    key click percent:  0    LED mask:  %s\\n" '
                               '"$(cat "$HOME/led" 2>/dev/null || echo 00000000)"')
        stub(self.bin, 'setxkbmap', 'cat "$HOME/xkb" 2>/dev/null')
        stub(self.bin, 'docker', log + '\ncase "$1" in ps) cat "$HOME/docker.ps" 2>/dev/null ;; esac')
        stub(self.bin, 'wpctl', log + '\n[ "$1" = get-volume ] && cat "$HOME/volume" 2>/dev/null; exit 0')
        stub(self.bin, 'locale', 'cat "$HOME/t_fmt" 2>/dev/null || echo "%H:%M:%S"')
        stub(self.bin, 'pgrep', 'exit 1')
        stub(self.bin, 'ip', 'echo "2: eth0    inet 10.0.2.15/24 brd 10.0.2.255 scope global eth0"')
        # abyss-bar's side
        stub(self.bin, 'xmenu', 'cat > "$HOME/menu.in"; cat "$HOME/pick" 2>/dev/null')
        stub(self.bin, 'dmenu', 'echo "dmenu $*" >> "$HOME/calls.log"; cat >> "$HOME/dmenu.in"; '
                                'cat "$HOME/dmenu.pick" 2>/dev/null')
        stub(self.bin, 'setsid', '[ "$1" = -f ] && shift; "$@"')
        for name in ('abyss-control-center', 'abyss-software', 'st', 'xdotool', 'notify-send',
                     'abyss-keyboard', 'abyss-priv'):
            stub(self.bin, name, log)
        self.sys = self.home / 'sys'
        self.proc = self.home / 'proc'
        write(self.proc / 'stat', 'cpu  100 0 50 1000 10 0 0 0 0 0\n')
        write(self.proc / 'meminfo', 'MemTotal:        3984588 kB\nMemFree:  1000 kB\n'
                                     'MemAvailable:    2621440 kB\n')
        write(self.proc / 'net/route', 'Iface\tDestination\tGateway\n')
        write(self.proc / 'net/wireless', 'Inter-| sta-|   Quality\n face | tus | link level noise\n')
        (self.sys / 'class/net').mkdir(parents=True)
        (self.sys / 'class/power_supply').mkdir(parents=True)
        self.services = self.home / 'service'
        self.services.mkdir()
        self.sock = None

    def iface(self, name, wireless=False):
        d = self.sys / 'class/net' / name
        (d / 'device').mkdir(parents=True)
        write(d / 'statistics/rx_bytes', '1000\n')
        write(d / 'statistics/tx_bytes', '500\n')
        write(d / 'operstate', 'up\n')
        if wireless:
            (d / 'wireless').mkdir()

    def docker_socket(self):
        path = str(self.home / 'docker.sock')
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(path)
        return path

    def file(self, name, text):
        write(self.home / name, text)

    def env(self, **extra):
        env = {'HOME': str(self.home), 'PATH': f'{self.bin}:{SYSTEM_PATH}', 'TZ': 'UTC',
               'LC_ALL': 'C', 'XDG_RUNTIME_DIR': str(self.home / 'run'), 'XDG_CONFIG_HOME': str(self.home / 'config'),
               'ABYSS_BAR_SYS': str(self.sys), 'ABYSS_BAR_PROC': str(self.proc),
               'ABYSS_BAR_SERVICES': str(self.services), 'ABYSS_BAR_NOW': str(NOW),
               'ABYSS_BAR_MARKERS': '1', 'DOCKER_HOST': f'unix://{self.home}/docker.sock'}
        env.update(extra)
        return env

    def calls(self):
        path = self.home / 'calls.log'
        return path.read_text() if path.exists() else ''

    def close(self):
        if self.sock:
            self.sock.close()
        shutil.rmtree(self.home, ignore_errors=True)


def blocks(status):
    """{marker byte: text of that block, status2d codes removed}"""
    out = {}
    for m in re.finditer(r'([\x01-\x1f])([^\x01-\x1f]*)', status):
        out[ord(m.group(1))] = re.sub(r'\^[^^]*\^', '', m.group(2)).strip()
    return out


@unittest.skipUnless(BASH5, 'dwm-statusbar needs bash 5')
class StatusbarTest(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox()
        self.addCleanup(self.box.close)
        self.box.file('xkb', 'rules:      evdev\nmodel:      pc105\nlayout:     us,ara\n'
                             'variant:    ,digits\noptions:    grp:alt_shift_toggle,caps:escape,grp_led:scroll\n')
        self.box.file('volume', 'Volume: 0.42\n')

    def status(self, **env):
        result = subprocess.run([BASH5, str(STATUSBAR), '--once'], env=self.box.env(**env),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        return result.stdout.rstrip('\n')

    def test_wifi_shows_the_network_name_and_signal(self):
        self.box.iface('wlan0', wireless=True)
        self.box.file('nmcli.dev', 'wlan0:wifi:connected:Home\\:Net\nlo:loopback:connected (externally):lo\n')
        write(self.box.proc / 'net/wireless', 'Inter-| sta-|   Quality\n face | tus | link level noise\n'
                                              ' wlan0: 0000   60.  -50.  -256 0 0 0 0 0 0\n')
        self.assertEqual(blocks(self.status())[1], '󰤨 Home:Net')
        write(self.box.proc / 'net/wireless', 'x\ny\n wlan0: 0000   20.  -80.  -256 0 0 0 0 0 0\n')
        self.assertEqual(blocks(self.status())[1], '󰤢 Home:Net')

    def test_long_or_odd_network_names_cannot_break_the_bar(self):
        self.box.iface('wlan0', wireless=True)
        self.box.file('nmcli.dev', 'wlan0:wifi:connected:^c#ff0000^A very long network name\n')
        text = blocks(self.status())[1]
        self.assertNotIn('^', text)
        self.assertTrue(text.endswith('…'), text)
        self.assertLessEqual(len(text), 2 + 16)

    def test_wired_and_offline(self):
        self.box.iface('eth0')
        self.box.file('nmcli.dev', 'eth0:ethernet:connected:Wired connection 1\n')
        self.assertEqual(blocks(self.status())[1], '󰈀 Wired')
        self.box.file('nmcli.dev', 'eth0:ethernet:unavailable:\n')
        self.assertEqual(blocks(self.status())[1], '󰤮 offline')

    def test_without_networkmanager_the_default_route_decides(self):
        self.box.iface('eth0')
        self.box.file('nm-down', '')
        self.assertEqual(blocks(self.status())[1], '󰤮 offline')
        write(self.box.proc / 'net/route', 'Iface\tDestination\tGateway\neth0\t00000000\t0202000A\n')
        self.assertEqual(blocks(self.status())[1], '󰈀 Wired')
        self.box.iface('wlan0', wireless=True)
        write(self.box.proc / 'net/route', 'Iface\tDestination\tGateway\nwlan0\t00000000\t0202000A\n')
        self.assertEqual(blocks(self.status())[1], '󰤨 Wi-Fi')

    def test_network_speed_is_optional(self):
        self.box.iface('eth0')
        self.box.file('nmcli.dev', 'eth0:ethernet:connected:Wired connection 1\n')
        self.assertNotIn('↓', self.status())
        write(self.box.home / 'config/abyss/bar.conf', 'SHOW_RATES=1\n')
        self.assertIn('↓0B ↑0B', blocks(self.status())[1])

    def test_keyboard_layout_follows_the_scroll_lock_led(self):
        self.assertEqual(blocks(self.status())[4], '󰌌 EN')
        self.box.file('led', '00000004')
        self.assertEqual(blocks(self.status())[4], '󰌌 AR')
        self.box.file('led', '00000002')                     # Num Lock only
        self.assertEqual(blocks(self.status())[4], '󰌌 EN')

    def test_keyboard_layout_from_xkb_switch(self):
        stub(self.box.bin, 'xkb-switch', 'echo "ara(digits)"')
        self.assertEqual(blocks(self.status())[4], '󰌌 AR')

    def test_keyboard_is_hidden_with_one_layout(self):
        self.box.file('xkb', 'layout:     us\noptions:    grp_led:scroll\n')
        self.assertNotIn(4, blocks(self.status()))

    def test_docker_only_while_its_service_runs(self):
        self.box.file('docker.ps', 'abc123\ndef456\n')
        self.assertNotIn(2, blocks(self.status()))           # no socket
        self.box.docker_socket()
        self.assertNotIn(2, blocks(self.status()))           # service not enabled
        (self.box.services / 'docker').mkdir()
        self.assertEqual(blocks(self.status())[2], '󰡨 2')
        self.box.file('docker.ps', '')
        self.assertEqual(blocks(self.status())[2], '󰡨 0')

    def test_passwords_icon(self):
        self.assertEqual(blocks(self.status())[3], '󰌋')
        write(self.box.home / 'config/abyss/bar.conf', 'SHOW_PASSWORDS=auto\n')
        if not shutil.which('pass', path=SYSTEM_PATH):
            self.assertNotIn(3, blocks(self.status()))
        stub(self.box.bin, 'pass', 'exit 0')
        self.assertEqual(blocks(self.status())[3], '󰌋')

    def test_sound_cpu_memory(self):
        b = blocks(self.status())
        self.assertEqual(b[5], '󰖀 42%')
        self.assertRegex(b[7], '^\uf2db \\d+%$')
        self.assertEqual(b[8], '󰍛 1.3/3.8G')
        self.box.file('volume', 'Volume: 0.42 [MUTED]\n')
        self.assertEqual(blocks(self.status())[5], '󰝟 mute')

    def test_clock_follows_the_locale_12_or_24_hours(self):
        self.assertEqual(blocks(self.status())[9], 'Wed 18 Nov 19:11')
        self.box.file('t_fmt', '%r\n')                   # en_US
        self.assertEqual(blocks(self.status())[9], 'Wed 18 Nov 7:11 PM')
        # LANG alone (Abyss sets en_US.UTF-8 for the language) keeps 24-hour
        self.assertEqual(blocks(self.status(LC_ALL='', LANG='en_US.UTF-8'))[9], 'Wed 18 Nov 19:11')
        self.assertEqual(blocks(self.status(LC_ALL='', LC_TIME='en_US.UTF-8'))[9], 'Wed 18 Nov 7:11 PM')
        write(self.box.home / 'config/abyss/bar.conf', "CLOCK_FORMAT='%Y-%m-%d %H:%M'\n")
        self.assertEqual(blocks(self.status())[9], '2026-11-18 19:11')

    def test_blocks_are_in_order_and_menu_is_last(self):
        self.box.iface('eth0')
        self.box.file('nmcli.dev', 'eth0:ethernet:connected:Wired connection 1\n')
        status = self.status()
        markers = [ord(c) for c in status if ord(c) < 32]
        self.assertEqual(markers, sorted(markers))
        self.assertEqual(markers[-1], 10)
        self.assertEqual(blocks(status)[10], 'Menu')

    def test_no_markers_for_a_dwm_without_statuscmd(self):
        status = self.status(ABYSS_BAR_MARKERS='0')
        self.assertFalse(any(ord(c) < 32 for c in status), repr(status))
        self.assertTrue(status.endswith('^b#a855f7^^c#090514^ Menu ^d^'))


class BlockNumbersTest(unittest.TestCase):
    """dwm-statusbar's markers and abyss-bar's table must agree."""

    def test_markers_match_abyss_bar(self):
        names = {'NET': 'network', 'DOCKER': 'docker', 'PASS': 'passwords', 'KBD': 'keyboard',
                 'SOUND': 'sound', 'BAT': 'battery', 'CPU': 'cpu', 'MEM': 'memory',
                 'CLOCK': 'clock', 'MENU': 'menu'}
        markers = {names[m]: int(n, 16) for m, n in
                   re.findall(r"M_([A-Z]+)=\$'\\x([0-9a-f]{2})'", STATUSBAR.read_text())}
        self.assertEqual(len(markers), 10)
        out = subprocess.run(['/bin/sh', str(BAR), '--blocks'], stdout=subprocess.PIPE, text=True, check=True).stdout
        table = {name: int(n) for n, name in (line.split() for line in out.splitlines())}
        self.assertEqual(markers, table)

    def test_dwm_hides_markers_and_maps_clicks(self):
        source = DWM_C.read_text() if DWM_C.exists() else DWM_PATCH.read_text()
        self.assertIn('statusblockat', source)
        self.assertIn('BLOCK_BUTTON', source)
        self.assertIn('"/usr/local/bin/abyss-bar", "--click"', source + (
            (ROOT / 'dwm/config.def.h').read_text() if (ROOT / 'dwm/config.def.h').exists() else ''))


class AbyssBarTest(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox()
        self.addCleanup(self.box.close)
        self.box.file('xkb', 'layout:     us,ara\noptions:    grp:alt_shift_toggle,grp_led:scroll\n')
        self.box.file('volume', 'Volume: 0.42\n')

    def click(self, block, button=None, pick='', **env):
        self.box.file('pick', pick + '\n' if pick else '')
        args = ['/bin/sh', str(BAR), '--click', str(block)] + ([str(button)] if button is not None else [])
        result = subprocess.run(args, env=self.box.env(**env), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def menu(self):
        path = self.box.home / 'menu.in'
        return path.read_text() if path.exists() else ''

    def test_menu_block_and_right_click_open_the_abyss_menu(self):
        self.click(10, 1)
        self.assertIn('abyss-control-center \n', self.box.calls())
        self.click(10, 2)
        self.assertIn('st \n', self.box.calls())
        for block in (1, 4, 9):
            (self.box.home / 'calls.log').unlink()
            self.click(block, 3)
            self.assertEqual(self.box.calls(), 'abyss-control-center \n')

    def test_unknown_block_does_nothing(self):
        self.click(42, 1)
        self.click(0, 1)
        self.assertEqual(self.box.calls(), '')

    def test_sound_scroll_middle_and_menu(self):
        self.click(5, 4)
        self.click(5, 5)
        self.click(5, 2)
        calls = self.box.calls()
        self.assertIn('wpctl set-volume -l 1.0 @DEFAULT_AUDIO_SINK@ 5%+', calls)
        self.assertIn('wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-', calls)
        self.assertIn('wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle', calls)
        self.click(5, 1, pick='cc:audio-gui')
        self.assertIn('Volume: 42%', self.menu())
        self.assertIn('abyss-control-center audio-gui', self.box.calls())

    def test_button_from_block_button_env(self):
        self.click(5, BLOCK_BUTTON='4')
        self.assertIn('5%+', self.box.calls())

    def test_network_menu(self):
        self.box.file('nmcli.dev', 'wlan0:wifi:connected:Home\nlo:loopback:connected (externally):lo\n')
        self.box.file('nmcli.wifi', '*:78\n')
        self.click(1, 1, pick='wifi-off')
        menu = self.menu()
        self.assertIn('Wi-Fi: Home  (78%)', menu)
        self.assertIn('Wi-Fi networks…\twifi-list', menu)
        self.assertIn('Network settings…\tcc:net-tui', menu)
        self.assertIn('nmcli radio wifi off', self.box.calls())

    def test_wifi_list_connects_with_a_hidden_password_prompt(self):
        self.box.file('nmcli.dev', 'wlan0:wifi:disconnected:\n')
        self.box.file('nmcli.wifi', ':40:WPA2:Cafe\n:80:WPA2:Home\\:5G\n:30::Open\n')
        self.box.file('dmenu.pick', '󰤨  Home:5G  80%  󰌾\n')
        self.click(1, 1, pick='wifi-list')
        listed = (self.box.home / 'dmenu.in').read_text().splitlines()
        self.assertEqual(listed[0], '󰤨  Home:5G  80%  󰌾')         # strongest first
        calls = self.box.calls()
        self.assertIn('dmenu -i -c -l 16', calls)
        self.assertRegex(calls, r'dmenu .* -P -p Password for Home:5G')
        self.assertIn('nmcli device wifi connect Home:5G password', calls)

    def test_keyboard(self):
        self.click(4, 1, pick='kbd-set:1')
        menu = self.menu()
        self.assertIn('Keyboard: English (US)', menu)
        self.assertIn('\U000f043e  English (US)\tkbd-set:0', menu)
        self.assertIn('\U000f043d  Arabic\tkbd-set:1', menu)
        self.assertIn('\t󰌌  View and edit shortcuts\tcc:shortcuts', menu)
        # without xkb-switch only Alt+Shift can switch: say so
        if not shutil.which('xkb-switch', path=SYSTEM_PATH):
            self.assertIn('notify-send -a Abyss Keyboard Press Alt+Shift', self.box.calls())
        stub(self.box.bin, 'xkb-switch', 'echo "xkb-switch $*" >> "$HOME/calls.log"; '
                                         '[ "$1" = -p ] && cat "$HOME/group"; exit 0')
        self.box.file('group', 'us\n')
        self.click(4, 1, pick='kbd-set:1')
        self.assertEqual(self.box.calls().count('xkb-switch -n'), 1)
        # already on Arabic: choosing it again does nothing
        self.box.file('group', 'ara(digits)\n')
        (self.box.home / 'calls.log').unlink()
        self.click(4, 1, pick='kbd-set:1')
        self.assertIn('\U000f043e  Arabic', self.menu())
        self.assertNotIn('xkb-switch -n', self.box.calls())
        self.click(4, 2)
        self.assertIn('xkb-switch -n', self.box.calls())

    def test_keyboard_led_without_xkb_switch(self):
        self.box.file('led', '00001004')
        self.click(4, 1)
        self.assertIn('\U000f043e  Arabic\tkbd-set:1', self.menu())

    def test_docker_menu(self):
        sock = self.box.home / 'docker.sock'
        sock.write_text('')
        self.box.file('docker.ps', 'abc123\tweb\tnginx\trunning\tUp 3 minutes\n'
                                   'def456\tdb\tpostgres\texited\tExited (0) 1 hour ago\n')
        self.click(2, 1, pick='dk-stop:abc123')
        menu = self.menu()
        self.assertIn('Docker · 1 running', menu)
        self.assertIn('󰆧  web  (nginx) · Up 3 minutes\n\t󰦪  Logs\tdk-logs:abc123', menu)
        self.assertIn('\t\t󰐊  Start\tdk-start:def456', menu)
        self.assertIn('docker stop abc123', self.box.calls())
        self.click(2, 1, pick='dk-stop:abc;reboot')                  # not an ID
        self.assertNotIn('reboot', self.box.calls())

    @unittest.skipIf(os.geteuid() == 0, 'root can write any socket')
    def test_docker_menu_outside_the_docker_group(self):
        sock = self.box.home / 'docker.sock'
        sock.write_text('')
        sock.chmod(0o400)
        self.click(2, 1)
        self.assertIn('join the docker group', self.menu())

    @unittest.skipIf(shutil.which('pass', path=SYSTEM_PATH), 'pass is installed here')
    def test_passwords_offers_to_install_pass(self):
        self.click(3, 1, pick='pass-install')
        self.assertIn('Install Password manager (pass)…\tpass-install', self.menu())
        self.assertIn("abyss-software --install pass pinentry-gtk xclip", self.box.calls())

    def test_passwords_menu_with_pass(self):
        stub(self.box.bin, 'pass', 'echo "pass $*" >> "$HOME/calls.log"')
        stub(self.box.bin, 'passmenu', 'echo "passmenu $*" >> "$HOME/calls.log"')
        self.click(3, 1)
        self.assertIn('Set up the password store…', self.menu())
        write(self.box.home / '.password-store/.gpg-id', 'ABC\n')
        write(self.box.home / '.password-store/web/github.gpg', '')
        self.click(3, 1, pick='pass-copy')
        self.assertIn('Passwords · 1 saved', self.menu())
        self.assertIn('passmenu -i -c -l 16', self.box.calls())

    def test_clock_menu(self):
        stub(self.box.bin, 'date', 'case "$1" in "+%-d") echo 18 ;; "+%:z") echo +00:00 ;; '
                                   '*) echo "Wednesday 18 November 2026" ;; esac')
        stub(self.box.bin, 'cal', 'printf "   November 2026\\nSu Mo Tu We Th Fr Sa\\n'
                                  ' 1  2  3  4  5  6  7\\n 8  9 10 11 12 13 14\\n15 16 17 18 19 20 21\\n'
                                  '22 23 24 25 26 27 28\\n29 30\\n\\n"')
        self.click(9, 1, pick='time-sync')
        menu = self.menu()
        self.assertIn('Wednesday 18 November 2026', menu)
        self.assertIn('  15 16 17[18]19 20 21\t-', menu)
        self.assertIn('  Su Mo Tu We Th Fr Sa\t-', menu)
        self.assertIn('Time zone…\ttz', menu)
        self.assertIn('chrony', menu)
        self.assertIn('st -t Clock', self.box.calls())

    def test_cpu_and_memory_open_the_system_monitor(self):
        self.click(7, 1)
        self.click(8, 1)
        self.assertEqual(self.box.calls(), 'abyss-control-center monitor\n' * 2)

    def test_dmenu_when_xmenu_is_missing(self):
        self.box.file('dmenu.pick', '󰒓  Keyboard settings › 󰌓  Test what keys send\n')
        self.click(4, 1, ABYSS_BAR_MENU='dmenu')
        self.assertFalse((self.box.home / 'menu.in').exists())
        listed = (self.box.home / 'dmenu.in').read_text()
        self.assertIn('\U000f043e  English (US)\n', listed)
        self.assertIn('󰒓  Keyboard settings › 󰌓  Test what keys send\n', listed)
        self.assertIn('abyss-control-center kbd-test', self.box.calls())


if __name__ == '__main__':
    unittest.main()
