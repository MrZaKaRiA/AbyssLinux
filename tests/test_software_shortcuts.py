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
        # Run as the desktop user whatever user runs the tests (CI is root):
        # shortcuts are only assigned outside root; what abyss-priv runs is root.
        for tool in ('abyss-priv', 'doas'):
            self.stub(tool, 'FAKE_ROOT=1 exec "$@"')
        self.stub('id', '[ "$1" = -u ] && [ -n "$FAKE_ROOT" ] && { echo 0; exit; }\n'
                        '[ "$1" = -u ] && { echo 1000; exit; }; echo uid=1000')

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
            f'[Desktop Entry]\nType=Application\nExec={cmd} %U\nTerminal={"true" if terminal else "false"}\n')

    def desktop_files(self, files):
        """Desktop files as Void's packages ship them: {file name: body}."""
        for name, body in files.items():
            (self.root / 'applications' / name).write_text(body)

    def audio_bundle(self, installed='pipewire\nwireplumber\npavucontrol\n'):
        """Void's audio packages: pipewire.desktop and wireplumber.desktop start
        the daemons (NoDisplay), pavucontrol's file has another name."""
        self.write('installed', installed)
        for cmd in ('pipewire', 'pipewire-pulse', 'wireplumber', 'pavucontrol'):
            self.stub(cmd, 'exit 0')
        self.desktop_files({
            'pipewire.desktop': '[Desktop Entry]\nName=PipeWire\nExec=pipewire\nTerminal=false\n'
                                'Type=Application\nNoDisplay=true\n',
            'pipewire-pulse.desktop': '[Desktop Entry]\nExec=pipewire-pulse\nType=Application\nNoDisplay=true\n',
            'wireplumber.desktop': '[Desktop Entry]\nExec=wireplumber\nTerminal=false\n'
                                   'Type=Application\nNoDisplay=true\n',
        })
        if 'pavucontrol' in installed:
            self.desktop_files({'org.pulseaudio.pavucontrol.desktop':
                                '[Desktop Entry]\nName=Volume Control\nExec=pavucontrol\nType=Application\n'})

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

    def test_audio_bundle_opens_the_mixer_not_the_pipewire_daemon(self):
        self.dwm()
        self.audio_bundle()
        self.assertTrue(self.labels()['audio-support'].endswith('✓ installed · Super+Alt+A'))
        self.software('--open', 'audio-support')
        self.assertEqual(self.log('setsid.log'), ['sh -c pavucontrol'])

    def test_wrong_shortcut_of_an_older_version_is_corrected_with_the_users_key(self):
        # 27.3.5 gave Audio support a shortcut that ran pipewire; the user then
        # moved it to Super+Alt+M. The record names the entry, not the program:
        # it stays as the user set it and now opens the mixer.
        self.dwm()
        self.audio_bundle()
        record = 'A\tsoftware-audio-support\t72\tm\tAudio support\texec:abyss-software --open audio-support'
        self.conf.parent.mkdir(parents=True)
        self.conf.write_text(record + '\n')
        (self.root / '.config/abyss/software-shortcuts').write_text('audio-support\n')
        self.assertTrue(self.labels()['audio-support'].endswith('✓ installed · Super+Alt+M'))
        self.assertEqual(self.conf_lines(), [record])
        self.software('--open', 'audio-support')
        self.assertEqual(self.log('setsid.log'), ['sh -c pavucontrol'])

    def test_bundle_with_only_hidden_desktop_files_loses_an_old_shortcut(self):
        # pipewire and wireplumber without the mixer: nothing to open, so the
        # shortcut an older version gave the daemon goes
        self.dwm()
        self.audio_bundle(installed='pipewire\nwireplumber\n')
        self.conf.parent.mkdir(parents=True)
        self.conf.write_text('A\tsoftware-audio-support\t72\ta\tAudio support\texec:abyss-software --open audio-support\n')
        (self.root / '.config/abyss/software-shortcuts').write_text('audio-support\n')
        label = self.labels()['audio-support']
        self.assertEqual(label, 'Audio support (PipeWire + mixer)  (partly installed, missing: pavucontrol)')
        self.assertEqual(self.conf_lines(), [])
        self.software('--open', 'audio-support')
        self.assertEqual(self.log('setsid.log'), [])

    def test_only_shown_applications_with_a_command_are_opened(self):
        self.write('catalog', 'Hidden\tpkg:a\nHidden2\tpkg:b\nLink\tpkg:c\nNo exec\tpkg:d\nAction\tpkg:e\n')
        for cmd in 'abcde':
            self.stub(cmd, 'exit 0')
        self.write('installed', 'a\nb\nc\nd\ne\n')
        self.desktop_files({
            'a.desktop': '[Desktop Entry]\nType=Application\nExec=a\nHidden=true\n',
            'b.desktop': '[Desktop Entry]\nType=Application\nExec=b\nNoDisplay = true\n',
            'c.desktop': '[Desktop Entry]\nType=Link\nURL=https://example.org\nExec=c\n',
            'd.desktop': '[Desktop Entry]\nType=Application\nExec=\n',
            # NoDisplay of an action is not the app's
            'e.desktop': '[Desktop Entry]\nType=Application\nExec=e --window %F\n'
                         '[Desktop Action x]\nExec=e --x\nNoDisplay=true\n',
        })
        env = {'ABYSS_SOFTWARE_CATALOG': str(self.root / 'catalog'), 'ABYSS_NO_SHORTCUTS': '1'}
        for key in ('hidden', 'hidden2', 'link', 'no-exec', 'action'):
            self.software('--open', key, env=env)
        self.assertEqual(self.log('setsid.log'), ['sh -c e --window'])

    def test_every_catalogue_bundle_opens_its_real_app(self):
        # the desktop files of Void's packages in the catalogue (aarch64,
        # November 2026): which app each bundle opens, or none
        self.dwm()
        self.audio_bundle(installed='')
        self.desktop_files({
            'firefox.desktop': '[Desktop Entry]\nType=Application\nExec=/usr/lib/firefox/firefox %u\n'
                               '[Desktop Action new-window]\nExec=/usr/lib/firefox/firefox --new-window %u\n',
            'chromium.desktop': '[Desktop Entry]\nExec=chromium %U\nTerminal=false\nType=Application\n',
            'virt-manager.desktop': '[Desktop Entry]\nExec=virt-manager\nType=Application\nTerminal=false\n',
            'vlc.desktop': '[Desktop Entry]\nExec=/usr/bin/vlc --started-from-file %U\nTryExec=/usr/bin/vlc\n'
                           'Terminal=false\nType=Application\n',
            'thunar.desktop': '[Desktop Entry]\nExec=thunar %U\nTerminal=false\nType=Application\n',
            'thunar-settings.desktop': '[Desktop Entry]\nExec=thunar-settings\nType=Application\n',
            'org.pulseaudio.pavucontrol.desktop': '[Desktop Entry]\nExec=pavucontrol\nType=Application\n',
            'lf.desktop': '[Desktop Entry]\nType=Application\nTerminal=true\nExec=lf\n',
            # sorts before zathura's own file and runs zathura too, hidden
            'org.pwmt.zathura-pdf-mupdf.desktop': '[Desktop Entry]\nType=Application\nExec=zathura %U\n'
                                                  'Terminal=false\nNoDisplay=true\n',
            'org.pwmt.zathura.desktop': '[Desktop Entry]\nType=Application\nExec=zathura %U\nTerminal=false\n',
            'mpv.desktop': '[Desktop Entry]\nType=Application\nTryExec=mpv\n'
                           'Exec=mpv --player-operation-mode=pseudo-gui -- %U\nTerminal=false\n',
            'org.gnupg.pinentry-qt.desktop': '[Desktop Entry]\nType=Application\nExec=/usr/bin/pinentry-qt\n'
                                             'NoDisplay=true\n',
        })
        commands = ('firefox chromium virt-manager vlc thunar pavucontrol pipewire wireplumber lf vim zathura mpv '
                    'qemu-system-aarch64 virsh docker git pass gpg pinentry-gtk-2 pinentry-qt xclip yt-dlp ffmpeg '
                    'bluetoothctl brightnessctl maim tmux fzf rg udisksctl').split()
        for cmd in commands:
            self.stub(cmd, 'exit 0')
        packages = set()
        for line in self.software('--list-entries', 'aarch64').splitlines():
            action = line.split('\t')[1]
            if action.startswith('pkg:'):
                packages.update(action[4:].split())
        self.write('installed', ''.join(p + '\n' for p in sorted(packages)))
        opened = {}
        for key in ('firefox', 'chromium', 'virtual-machines', 'docker-engine', 'vlc-media-player',
                    'external-storage', 'git', 'audio-support', 'terminal-workspace', 'passwords',
                    'writing-and-research', 'media-tools', 'bluetooth-support', 'laptop-brightness-controls',
                    'screenshot-capture'):
            (self.root / 'setsid.log').unlink(missing_ok=True)
            self.software('--open', key)
            opened[key] = self.log('setsid.log')
        self.assertEqual(opened, {
            'firefox': ['sh -c /usr/lib/firefox/firefox'],
            'chromium': ['sh -c chromium'],
            'virtual-machines': ['sh -c virt-manager'],
            'docker-engine': [],
            'vlc-media-player': ['sh -c /usr/bin/vlc --started-from-file'],
            'external-storage': ['sh -c thunar'],
            'git': [],
            'audio-support': ['sh -c pavucontrol'],
            'terminal-workspace': ['st -t Terminal workspace -e sh -c lf'],    # Void's vim has no desktop file
            'passwords': [],
            'writing-and-research': ['sh -c zathura'],
            'media-tools': ['sh -c mpv --player-operation-mode=pseudo-gui --'],  # a bare "mpv" only prints help
            'bluetooth-support': [],
            'laptop-brightness-controls': [],
            'screenshot-capture': [],
        })

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
