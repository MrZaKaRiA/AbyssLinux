"""Install software: installed state of every catalogue entry (Void packages
and vendor apps), what clicking an installed entry offers, Git with the
editors, and the Super+Alt shortcut each installed app gets (assigned
without conflicts, shown in the menu, cleared with the app). dwm is
simulated by an abyss-key-capture stub; runs without X or xbps."""
import io
import os
from pathlib import Path
import shutil
import sys
import tarfile
import unittest

from test_software_packages import SOFTWARE, StubbedTest

# A running Abyss dwm, as abyss-key-capture sees it: some defaults (B), the
# application shortcuts of the user's file (A) unless $HOME/reject says dwm
# refused the file, and other programs' grabs in $HOME/grabbed ("72 v").
KEY_CAPTURE = r'''#!PYTHON
import os, sys
home = os.environ['HOME']
conf = os.path.join(os.environ.get('XDG_CONFIG_HOME') or os.path.join(home, '.config'), 'abyss/shortcuts.conf')
args = sys.argv[1:]
with open(os.path.join(home, 'keycapture.log'), 'a') as f: f.write(' '.join(args) + '\n')
if args == ['--list']:
    for mod, key, label in [('64', 'Return', 'Open terminal'), ('72', 'Return', 'Open alternate terminal'),
                            ('64', 'c', 'Open VS Code'), ('65', 'c', 'Close window'), ('65', 'q', 'Log out'),
                            ('72', '0', 'Toggle gaps')]:
        print('\t'.join(['B', mod, key, mod, key, label]))
    if os.path.exists(conf) and not os.path.exists(os.path.join(home, 'reject')):
        for line in open(conf):
            if line.startswith('A\t'): print(line.rstrip('\n'))
elif args == ['--reload']:
    pass
elif args[:1] == ['--probe']:
    grabbed = open(os.path.join(home, 'grabbed')).read().split('\n') if os.path.exists(os.path.join(home, 'grabbed')) else []
    sys.exit(3 if ' '.join(args[1:]) in grabbed else 0)
else:
    sys.exit(2)
'''

VSCODE_RECORD = 'A\tsoftware-vscode\t72\tv\tVisual Studio Code\texec:abyss-software --open vscode'


class SoftwareShortcutsTest(StubbedTest):
    def setUp(self):
        super().setUp()
        for tool in 'tar gzip ln readlink cmp install uniq'.split():
            found = shutil.which(tool, path='/usr/bin:/bin:/usr/sbin:/sbin')
            if found and not (self.bin / tool).exists():
                (self.bin / tool).symlink_to(found)
        self.sysroot = self.root / 'sysroot'
        self.env.update(ABYSS_ROOT=str(self.sysroot), ABYSS_RELOAD_POLL='0',
                        ABYSS_APPLICATIONS_DIR=str(self.root / 'applications'))
        (self.root / 'applications').mkdir()
        self.conf = self.root / '.config/abyss/shortcuts.conf'

    # helpers -------------------------------------------------------------
    def dwm(self):
        path = self.bin / 'abyss-key-capture'
        path.write_text(KEY_CAPTURE.replace('PYTHON', sys.executable, 1))
        path.chmod(0o755)

    def executable(self, path, body='exit 0'):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('#!/bin/sh\n' + body + '\n')
        path.chmod(0o755)

    def install_vscode_files(self):
        self.executable(self.root / '.local/opt/vscode/code')
        (self.root / '.local/bin').mkdir(parents=True, exist_ok=True)
        (self.root / '.local/bin/code').symlink_to(self.root / '.local/opt/vscode/code')
        (self.root / '.local/share/applications').mkdir(parents=True, exist_ok=True)
        (self.root / '.local/share/applications/abyss-vscode.desktop').write_text('[Desktop Entry]\n')

    def desktop_app(self, cmd, terminal=False):
        self.stub(cmd, 'exit 0')
        (self.root / f'applications/{cmd}.desktop').write_text(
            f'[Desktop Entry]\nExec={cmd} %U\nTerminal={"true" if terminal else "false"}\n')

    def states(self):
        return {line.split('\t')[0]: line.split('\t')[1] for line in self.software('--installed').splitlines()}

    def labels(self):
        rows = self.software('--installed').splitlines()
        return {r.split('\t')[0]: r.split('\t')[2] for r in rows}

    def conf_lines(self):
        return self.conf.read_text().splitlines() if self.conf.exists() else []

    def run_menu(self, *answers):
        self.write('dmenu.answers', ''.join(a + '\n' for a in answers))
        return self.software()

    def prompts(self):
        return [l for l in self.log('dmenu.log') if l.startswith('## ')]

    # installed detection ---------------------------------------------------
    def test_nothing_installed_is_shown_as_not_installed(self):
        states = self.states()
        for key in ('vscode', 'cursor', 'artcraft', 'ollama', 'claude-code', 'opencode', 'chrome',
                    'antigravity', 'firefox', 'git'):
            self.assertEqual(states[key], 'none', key)
        self.assertEqual(states['chatgpt'], '-')      # a web link has no installed state
        self.assertEqual(states['search'], '-')

    def test_vendor_apps_are_found_where_their_installers_put_them(self):
        home, sysroot = self.root, self.sysroot
        self.install_vscode_files()
        self.executable(home / '.local/opt/cursor.AppImage')
        self.executable(home / '.local/opt/artcraft-launcher.AppImage')
        self.executable(sysroot / 'usr/local/bin/ollama')
        self.executable(home / '.local/bin/claude')
        self.executable(home / '.opencode/bin/opencode')
        self.executable(sysroot / 'usr/bin/google-chrome-stable')
        self.executable(home / '.local/opt/antigravity/antigravity')
        states = self.states()
        for key in ('vscode', 'cursor', 'artcraft', 'ollama', 'claude-code', 'opencode', 'chrome', 'antigravity'):
            self.assertEqual(states[key], 'all', key)

    def test_vscode_is_found_in_system_and_flatpak_locations(self):
        self.executable(self.sysroot / 'usr/bin/code')
        self.assertEqual(self.states()['vscode'], 'all')
        (self.sysroot / 'usr/bin/code').unlink()
        self.executable(self.sysroot / 'usr/bin/code-oss')     # Void's own vscode package
        self.assertEqual(self.states()['vscode'], 'all')
        (self.sysroot / 'usr/bin/code-oss').unlink()
        self.stub('flatpak', '[ "$1 $2" = "info com.visualstudio.code" ]')
        self.assertEqual(self.states()['vscode'], 'all')

    def test_a_dangling_link_is_not_an_installed_app(self):
        (self.root / '.local/bin').mkdir(parents=True)
        (self.root / '.local/bin/claude').symlink_to(self.root / 'gone')
        self.assertEqual(self.states()['claude-code'], 'none')

    def test_package_entries_are_all_part_or_none(self):
        self.write('installed', 'firefox\nmpv\ngit\n')
        states = self.states()
        self.assertEqual(states['firefox'], 'all')
        self.assertEqual(states['git'], 'all')
        self.assertEqual(states['media-tools'], 'part:yt-dlp ffmpeg xclip')
        self.assertEqual(states['vlc-media-player'], 'none')

    def test_git_is_in_the_catalogue(self):
        self.assertIn('Git (version control)\tpkg:git', self.software('--list-entries', 'aarch64'))
        self.assertIn('Git (version control)\tpkg:git', self.software('--list-entries', 'x86_64'))

    # shortcuts ---------------------------------------------------------------
    def test_installed_app_gets_super_alt_initial_and_shows_it(self):
        self.dwm()
        self.install_vscode_files()
        labels = self.labels()
        self.assertEqual(labels['vscode'], 'Visual Studio Code (latest stable)  ✓ installed · Super+Alt+V')
        self.assertEqual(self.conf_lines(), [VSCODE_RECORD])
        self.assertIn('--reload', self.log('keycapture.log'))
        # once assigned it is kept, not assigned again
        self.labels()
        self.assertEqual(self.conf_lines(), [VSCODE_RECORD])

    def test_shortcut_avoids_dwm_user_and_other_programs_combinations(self):
        self.dwm()
        self.install_vscode_files()
        self.conf.parent.mkdir(parents=True)
        self.conf.write_text('A\tapp-1\t72\tv\tMy editor\texec:vim\n')    # the user's own
        self.write('grabbed', '72 s\n')                                    # another program
        self.assertTrue(self.labels()['vscode'].endswith('✓ installed · Super+Alt+C'))
        self.assertIn('A\tapp-1\t72\tv\tMy editor\texec:vim', self.conf_lines())

    def test_two_apps_with_the_same_initial_get_different_keys(self):
        self.dwm()
        self.write('installed', 'vlc\n')
        self.desktop_app('vlc')
        self.install_vscode_files()
        labels = self.labels()
        self.assertTrue(labels['vlc-media-player'].endswith('· Super+Alt+V'), labels['vlc-media-player'])
        self.assertTrue(labels['vscode'].endswith('· Super+Alt+S'), labels['vscode'])
        keys = [tuple(l.split('\t')[2:4]) for l in self.conf_lines()]
        self.assertEqual(len(keys), len(set(keys)))

    def test_falls_back_to_super_alt_shift_when_every_letter_is_taken(self):
        self.dwm()
        self.install_vscode_files()
        self.write('grabbed', ''.join(f'72 {c}\n' for c in 'abcdefghijklmnopqrstuvwxyz'))
        self.assertTrue(self.labels()['vscode'].endswith('· Super+Alt+Shift+V'))

    def test_bundle_without_an_app_gets_no_shortcut(self):
        self.dwm()
        self.write('installed', 'bluez\ngit\n')
        labels = self.labels()
        self.assertEqual(labels['bluetooth-support'], 'Bluetooth support  ✓ installed')
        self.assertEqual(labels['git'], 'Git (version control)  ✓ installed')
        self.assertEqual(self.conf_lines(), [])

    def test_package_app_gets_a_shortcut_and_terminal_apps_open_in_a_terminal(self):
        self.dwm()
        self.write('installed', 'firefox\nvim\nlf\nfzf\nripgrep\ntmux\n')
        self.desktop_app('firefox')
        self.desktop_app('vim', terminal=True)
        labels = self.labels()
        self.assertTrue(labels['firefox'].endswith('✓ installed · Super+Alt+F'))
        self.assertTrue(labels['terminal-workspace'].endswith('✓ installed · Super+Alt+T'))
        self.software('--open', 'firefox')
        self.software('--open', 'terminal-workspace')
        self.assertEqual(self.log('setsid.log'), ['sh -c firefox', 'st -t Terminal workspace -e sh -c vim'])

    def test_no_shortcuts_without_a_running_abyss_dwm(self):
        self.install_vscode_files()
        self.assertEqual(self.labels()['vscode'], 'Visual Studio Code (latest stable)  ✓ installed')
        self.assertFalse(self.conf.exists())

    def test_rejected_file_is_put_back(self):
        self.dwm()
        self.install_vscode_files()
        self.conf.parent.mkdir(parents=True)
        self.conf.write_text('B\t64\tReturn\t64\tF2\n')
        self.write('reject', '')
        self.labels()
        self.assertEqual(self.conf.read_text(), 'B\t64\tReturn\t64\tF2\n')

    def test_cleared_shortcut_stays_cleared(self):
        self.dwm()
        self.install_vscode_files()
        self.labels()
        self.conf.write_text('')                       # the user removed it in the editor
        self.assertEqual(self.labels()['vscode'], 'Visual Studio Code (latest stable)  ✓ installed')
        self.assertEqual(self.conf_lines(), [])

    def test_removing_the_app_removes_its_shortcut_and_reinstalling_gives_one(self):
        self.dwm()
        self.install_vscode_files()
        self.labels()
        out = self.software('--run-vendor-remove', 'vscode')
        self.assertEqual(self.status, 0, out)
        self.assertIn('Removed: Visual Studio Code', out)
        self.assertIn('Keyboard shortcut Super+Alt+V (Visual Studio Code) removed', out)
        self.assertFalse((self.root / '.local/opt/vscode').exists())
        self.assertFalse(os.path.lexists(self.root / '.local/bin/code'))
        self.assertFalse((self.root / '.local/share/applications/abyss-vscode.desktop').exists())
        self.assertEqual(self.conf_lines(), [])
        self.assertEqual((self.root / '.config/abyss/software-shortcuts').read_text(), '')
        self.install_vscode_files()
        self.labels()
        self.assertEqual(self.conf_lines(), [VSCODE_RECORD])

    def test_package_install_and_remove_report_the_shortcut(self):
        self.dwm()
        self.desktop_app('firefox')
        out = self.software('--run-install', '--yes', 'firefox')
        self.assertEqual(self.status, 0, out)
        self.assertIn('Installed: firefox', out)
        self.assertIn('Keyboard shortcut: Super+Alt+F opens Firefox', out)
        self.stub('xbps-remove', '''printf 'remove %s\\n' "$*" >> "$HOME/xbps.log"; : > "$HOME/installed"''')
        out = self.software('--run-remove', 'firefox')
        self.assertIn('Removed: firefox', out)
        self.assertIn('Keyboard shortcut Super+Alt+F (Firefox) removed', out)
        self.assertEqual(self.conf_lines(), [])

    def test_shortcut_opens_the_app_wherever_it_is_installed(self):
        self.install_vscode_files()
        self.software('--open', 'vscode')
        self.assertEqual(self.log('setsid.log'), [f"sh -c '{self.root}/.local/opt/vscode/code'"])
        self.executable(self.root / '.local/opt/cursor.AppImage')
        self.software('--open', 'cursor')
        self.assertIn('--appimage-extract-and-run', self.log('setsid.log')[-1])
        self.executable(self.root / '.local/bin/claude')
        self.software('--open', 'claude-code')
        self.assertEqual(self.log('setsid.log')[-1], f"st -t Claude Code CLI -e sh -c '{self.root}/.local/bin/claude'")

    def test_shortcut_of_a_removed_app_explains(self):
        self.software('--open', 'vscode')
        self.assertEqual(self.status, 1)
        self.assertIn('Visual Studio Code is not installed', '\n'.join(self.log('notify.log')))

    # clicking an entry -------------------------------------------------------
    def test_installed_vscode_offers_open_update_git_remove_and_shortcut(self):
        self.dwm()
        self.install_vscode_files()
        self.run_menu('Visual Studio Code (latest stable)  ✓ installed · Super+Alt+V', 'Open Visual Studio Code')
        menu = self.log('dmenu.log')
        start = menu.index('## -i -c -l 13 -fn JetBrainsMono Nerd Font:size=10 -nb #0d0b18 -nf #f3e8ff '
                           '-sb #a855f7 -sf #090514 -p Visual Studio Code: installed')
        self.assertEqual(menu[start + 1:start + 7], ['Open Visual Studio Code', 'Update',
                                                     'Install Git (Source Control needs it)', 'Remove',
                                                     'Change shortcut…', 'Back'])
        self.assertEqual(self.log('setsid.log'), [f"sh -c '{self.root}/.local/opt/vscode/code'"])

    def test_installed_vscode_update_and_remove_open_a_terminal(self):
        self.install_vscode_files()
        self.run_menu('Visual Studio Code (latest stable)  ✓ installed', 'Update')
        self.assertRegex(self.log('setsid.log')[-1], r"^st -t Update Visual Studio Code -e sh -c /bin/sh '.*' --run-vendor-install vscode ?;")
        self.run_menu('Visual Studio Code (latest stable)  ✓ installed', 'Remove', 'Remove Visual Studio Code')
        self.assertRegex(self.log('setsid.log')[-1], r"--run-vendor-remove vscode;")

    def test_installed_vscode_can_add_git(self):
        self.install_vscode_files()
        self.run_menu('Visual Studio Code (latest stable)  ✓ installed', 'Install Git (Source Control needs it)')
        self.assertRegex(self.log('setsid.log')[-1], r"--run-install git;")

    def test_with_git_installed_vscode_does_not_offer_it(self):
        self.write('installed', 'git\n')
        self.install_vscode_files()
        self.run_menu('Visual Studio Code (latest stable)  ✓ installed', 'Back')
        self.assertNotIn('Install Git (Source Control needs it)', self.log('dmenu.log'))

    def test_change_shortcut_opens_the_editor_for_this_app(self):
        self.dwm()
        self.install_vscode_files()
        self.run_menu('Visual Studio Code (latest stable)  ✓ installed · Super+Alt+V', 'Change shortcut…')
        self.assertEqual(self.log('setsid.log')[-1], 'abyss-shortcut-editor --app software-vscode '
                                                     'Visual Studio Code exec:abyss-software --open vscode')
        self.assertEqual((self.root / '.config/abyss/software-shortcuts').read_text(), 'vscode\n')

    def test_vscode_install_offers_git_and_runs_in_a_terminal(self):
        self.run_menu('Visual Studio Code (latest stable)', 'Install Visual Studio Code + Git (Source Control needs Git)')
        self.assertIn('Install Visual Studio Code only', self.log('dmenu.log'))
        self.assertRegex(self.log('setsid.log')[-1],
                         r"^st -t Install Visual Studio Code -e sh -c /bin/sh '.*' --run-vendor-install vscode --with-git;")
        self.run_menu('Cursor (latest AppImage)', 'Install Cursor only')
        self.assertRegex(self.log('setsid.log')[-1], r"--run-vendor-install cursor ?;")

    def test_vscode_install_without_git_question_when_git_is_there(self):
        self.write('installed', 'git\n')
        self.run_menu('Visual Studio Code (latest stable)')
        self.assertRegex(self.log('setsid.log')[-1], r"--run-vendor-install vscode ?;")

    def test_vendor_install_terminal_installs_git_then_vscode_and_its_shortcut(self):
        self.dwm()
        archive = self.root / 'code.tar.gz'
        data = b'#!/bin/sh\nexit 0\n'
        with tarfile.open(archive, 'w:gz') as tar:
            info = tarfile.TarInfo('VSCode-linux-arm64/code')
            info.size, info.mode = len(data), 0o755
            tar.addfile(info, io.BytesIO(data))
        self.stub('curl', f'''while [ $# -gt 0 ]; do [ "$1" = -o ] && cp '{archive}' "$2"; shift; done''')
        out = self.software('--run-vendor-install', 'vscode', '--with-git')
        self.assertEqual(self.status, 0, out)
        self.assertIn('git', self.installs()[-1])
        self.assertIn('Installed: git', out)
        self.assertIn(f'Installed: Visual Studio Code ({self.root}/.local/opt/vscode/code)', out)
        self.assertIn('Keyboard shortcut: Super+Alt+V opens Visual Studio Code', out)
        self.assertEqual(self.conf_lines(), [VSCODE_RECORD])
        self.assertLess(out.index('Installed: git'), out.index('Downloading the latest stable VS Code'))

    def test_failed_vendor_download_is_reported(self):
        self.stub('curl', 'exit 22')
        out = self.software('--run-vendor-install', 'vscode')
        self.assertNotEqual(self.status, 0)
        self.assertIn('Download failed: Could not download VS Code from Microsoft.', out)
        self.assertIn('Not installed: Visual Studio Code', out)

    def test_system_wide_vendor_install_is_not_removed_here(self):
        self.executable(self.sysroot / 'usr/bin/code')
        self.run_menu('Visual Studio Code (latest stable)  ✓ installed', 'Back')
        self.assertNotIn('Remove', self.log('dmenu.log'))


if __name__ == '__main__':
    unittest.main()
