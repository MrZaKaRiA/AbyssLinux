"""Check the software installer: every package name it can install exists in
Void for x86_64 and aarch64, and the install path copes with a busy package
database, flaky networks and missing packages. Runs without X or xbps."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / 'custom-overlay/usr/local/bin'
SOFTWARE = Path(os.environ.get('ABYSS_SOFTWARE', BIN / 'abyss-software')).resolve()
CENTER = Path(os.environ.get('ABYSS_CENTER', BIN / 'abyss-control-center')).resolve()
SETUP = Path(os.environ.get('ABYSS_SETUP', BIN / 'abyss-setup')).resolve()
BAR = Path(os.environ.get('ABYSS_BAR', BIN / 'abyss-bar')).resolve()
# The shell helpers ship in abyss-desktop (AbyssLinuxPMR); found next to this
# checkout, inside the PMR checkout itself, or through ABYSS_PROFILE.
PROFILE = os.environ.get('ABYSS_PROFILE') or next(
    (str(p) for p in (ROOT / 'srcpkgs/abyss-desktop/files/zz-abyss-cli.sh',
                      ROOT.parent / 'AbyssLinuxPMR/srcpkgs/abyss-desktop/files/zz-abyss-cli.sh')
     if p.is_file()), '')
FIXTURES = Path(__file__).resolve().parent / 'fixtures'
ARCHES = ('x86_64', 'aarch64')

TOOLS = ('sh bash awk sed head tail cat cp rm mv mkdir tr cut sort grep sleep mktemp tee '
         'env id dirname basename chmod find touch').split()


# CI sets this to a directory holding the live <arch>-repodata and
# nonfree-<arch>-repodata files, to catch packages renamed in Void since the
# fixture was made.
LIVE_REPODATA = os.environ.get('ABYSS_VOID_REPODATA')


def live_packages(arch):
    import io, plistlib, tarfile
    names = set()
    for path in sorted(Path(LIVE_REPODATA).glob(f'*{arch}-repodata')):
        raw = subprocess.run(['zstd', '-dc', str(path)], check=True, stdout=subprocess.PIPE).stdout
        with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
            index = plistlib.loads(tar.extractfile('index.plist').read())
        names.update(index)
        for info in index.values():          # virtual packages resolve through provides
            names.update(re.sub(r'-[^-]+$', '', p) for p in info.get('provides', []) or [])
    assert names, f'no repodata for {arch} in {LIVE_REPODATA}'
    return names


def known_packages(arch):
    """Names this project references that exist in Void for ARCH (the fixture
    holds only those names, generated from the real repodata)."""
    if LIVE_REPODATA:
        return live_packages(arch)
    path = FIXTURES / f'void-packages-{arch}.txt'
    return {line.strip() for line in path.read_text().splitlines()
            if line.strip() and not line.startswith('#')}


def referenced_packages(arch):
    """Every package name the scripts can pass to xbps-install on ARCH."""
    result = subprocess.run(['/bin/sh', str(SOFTWARE), '--list-entries', arch],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    names = {}
    for line in result.stdout.splitlines():
        label, action = line.split('\t', 1)
        if action.startswith('pkg:'):
            for name in action[4:].split():
                names[name] = f'abyss-software: {label}'
    for name in re.findall(r"abyss-software --install '([^']+)'", CENTER.read_text()):
        for word in name.split():
            names[word.split('@')[0]] = 'abyss-control-center: install-audio'
    # the status bar's passwords menu installs pass
    for word in re.search(r"^PASS_PACKAGES='([^']+)'", BAR.read_text(), re.M).group(1).split():
        names[word] = 'abyss-bar: passwords'
    setup = SETUP.read_text()
    names['void-repo-nonfree'] = 'abyss-setup: optional repositories'
    if arch == 'x86_64':                      # abyss-setup offers multilib on x86_64 only
        assert 'Multilib is available only on x86_64' in setup
        names['void-repo-multilib'] = 'abyss-setup: optional repositories'
    return names


class PackageNamesTest(unittest.TestCase):
    def test_every_offered_package_exists_in_void(self):
        for arch in ARCHES:
            known = known_packages(arch)
            for name, where in referenced_packages(arch).items():
                with self.subTest(arch=arch, package=name):
                    self.assertTrue(name in known, f'{name} ({where}) is not a Void package on {arch}')

    def test_menu_offers_the_same_bundles_on_both_architectures(self):
        # Nothing in the menu is single-architecture today; a new entry that is
        # must be marked in the catalog so it is hidden where it does not exist.
        for arch in ARCHES:
            out = subprocess.run(['/bin/sh', str(SOFTWARE), '--list-entries', arch],
                                 stdout=subprocess.PIPE, text=True, check=True).stdout
            self.assertIn('External storage (udisks + GVFS)\tpkg:udisks2 gvfs Thunar', out)
            self.assertIn('Audio support (PipeWire + mixer)\tpkg:pipewire wireplumber pavucontrol', out)
            self.assertIn('about 1.8 GB download', out)


# Stub xbps tools. State lives in $HOME so each test sets it up with files:
#   sync-fail     number of syncs that still fail (with the message in sync-error)
#   missing       names xbps-query -R does not know
#   broken        names whose dry run fails (unresolvable dependency)
#   size          download size in bytes printed per package by dry runs
XBPS_INSTALL = r'''printf '%s\n' "$*" >> "$HOME/xbps.log"
case " $* " in *" -S "*)
    n=$(cat "$HOME/sync-fail" 2>/dev/null || echo 0)
    if [ "$n" -gt 0 ]; then
        echo $((n - 1)) > "$HOME/sync-fail"
        echo "[*] Updating repository \`https://repo-default.voidlinux.org/current/aarch64/aarch64-repodata' ..."
        cat "$HOME/sync-error" >&2
        exit 0
    fi
    echo "[*] Updating repository \`https://repo-default.voidlinux.org/current/aarch64/aarch64-repodata' ..."
    exit 0 ;;
esac
dry=; for a; do [ "$a" = -n ] && dry=1; done
for a; do
    case $a in -*) continue ;; esac
    if grep -qx "$a" "$HOME/broken" 2>/dev/null; then echo "$a: MISSING libfoo>=1" >&2; exit 19; fi
done
if [ -n "$dry" ]; then
    for a; do case $a in -*) ;; *) echo "$a-1.0_1 install aarch64 https://repo 2000 $(cat "$HOME/size" 2>/dev/null || echo 1000)" ;; esac; done
    exit 0
fi
[ -e "$HOME/install-fail" ] && exit 1
[ -e "$HOME/decline" ] && { echo 'Aborting!'; exit 0; }
for a; do case $a in -*) ;; *) echo "$a" >> "$HOME/installed" ;; esac; done
echo installed "$@"'''
XBPS_QUERY = r'''printf '%s\n' "$*" >> "$HOME/query.log"
if [ "$1" = -l ]; then
    while read -r n; do echo "ii $n-1.0_1 description"; done < "$HOME/installed" 2>/dev/null
    exit 0
fi
# -L: the repositories and their package counts (-1: no lists on disk)
if [ "$1" = -L ]; then cat "$HOME/repos" 2>/dev/null || echo "   8 https://repo-default.voidlinux.org/current/aarch64 (RSA signed)"; exit 0; fi
if [ "$1" != -R ]; then grep -qx "$1" "$HOME/installed" 2>/dev/null; exit $(( $? ? 2 : 0 )); fi
grep -qx "$2" "$HOME/missing" 2>/dev/null && exit 2
echo "pkgver: $2-1.0_1"'''
# pgrep reports a running xbps-install while $HOME/busy holds a positive count.
PGREP = r'''n=$(cat "$HOME/busy" 2>/dev/null || echo 0)
printf '%s\n' "$*" >> "$HOME/pgrep.log"
case "$*" in *xbps-install*) ;; *) exit 1 ;; esac
[ "$n" -gt 0 ] || exit 1
echo $((n - 1)) > "$HOME/busy"; exit 0'''
DMENU = '''{ echo "## $*"; cat; } >> "$HOME/dmenu.log"
a="$HOME/dmenu.answers"
[ -s "$a" ] || exit 1
head -n 1 "$a"
tail -n +2 "$a" > "$a.new"; mv "$a.new" "$a"'''


class StubbedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        for tool in TOOLS:
            found = shutil.which(tool, path='/usr/bin:/bin:/usr/sbin:/sbin')
            if found:
                (self.bin / tool).symlink_to(found)
        self.stub('xbps-install', XBPS_INSTALL)
        self.stub('xbps-query', XBPS_QUERY)
        self.stub('pgrep', PGREP)
        self.stub('uname', 'echo aarch64')
        self.stub('abyss-priv', 'exec "$@"')
        self.stub('xbps-remove', '''printf 'remove %s\\n' "$*" >> "$HOME/xbps.log"''')
        self.stub('doas', 'exec "$@"')
        self.stub('dmenu', DMENU)
        self.stub('notify-send', '''printf '%s\\n' "$*" >> "$HOME/notify.log"''')
        self.stub('setsid', '[ "$1" = -f ] && shift; printf \'%s\\n\' "$*" >> "$HOME/setsid.log"')
        self.env = {'HOME': str(self.root), 'PATH': str(self.bin), 'TMPDIR': str(self.root),
                    'ABYSS_RETRY_PAUSE': '0', 'ABYSS_LOCK_POLL': '0',
                    'ABYSS_SYNC_STAMP': str(self.root / 'synced')}

    def stub(self, name, body):
        path = self.bin / name
        if path.is_symlink():
            path.unlink()
        path.write_text('#!/bin/sh\n' + body + '\n')
        path.chmod(0o755)

    def write(self, name, text):
        (self.root / name).write_text(text)

    def log(self, name):
        path = self.root / name
        return path.read_text().splitlines() if path.exists() else []

    def software(self, *args, env=None):
        result = subprocess.run(['/bin/sh', str(SOFTWARE), *args], env={**self.env, **(env or {})},
                                cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, timeout=60)
        self.status, self.output = result.returncode, result.stdout
        return result.stdout

    def installs(self):
        return [line for line in self.log('xbps.log') if not line.startswith(('-S', '-n'))]


class InstallerTest(StubbedTest):

    # Architecture gating -------------------------------------------------
    def test_single_architecture_entries_are_hidden_elsewhere_and_labelled(self):
        self.write('catalog', 'Both\tpkg:a b@x86_64 c@aarch64\n'
                              'Intel only\tpkg:steam\tx86_64\n'
                              'Only x86 parts\tpkg:x@x86_64\n'
                              'Installer\tvscode\n')
        env = {'ABYSS_SOFTWARE_CATALOG': str(self.root / 'catalog')}
        arm = self.software('--list-entries', env=env)       # uname says aarch64
        self.assertEqual(arm.splitlines(), ['Both\tpkg:a c', 'Installer\tvscode'])
        intel = self.software('--list-entries', 'x86_64', env=env)
        self.assertEqual(intel.splitlines(), ['Both\tpkg:a b', 'Intel only (only on x86_64)\tpkg:steam',
                                              'Only x86 parts\tpkg:x', 'Installer\tvscode'])

    def test_xbps_architecture_wins_over_uname_and_musl_is_ignored(self):
        self.stub('xbps-uhelper', 'echo x86_64-musl')
        self.write('catalog', 'Intel only\tpkg:steam\tx86_64\n')
        out = self.software('--list-entries', env={'ABYSS_SOFTWARE_CATALOG': str(self.root / 'catalog')})
        self.assertIn('Intel only (only on x86_64)', out)

    def test_menu_install_drops_packages_missing_on_this_architecture(self):
        self.software('--install', 'a b@x86_64 c')
        self.assertEqual(len(self.log('setsid.log')), 1)
        self.assertRegex(self.log('setsid.log')[0], r"--run-install a c;")

    # Lock detection -------------------------------------------------------
    def test_waits_with_a_clear_message_while_another_install_runs(self):
        self.write('busy', '3')
        out = self.software('--run-install', '--yes', 'maim')
        self.assertEqual(self.status, 0, out)
        self.assertIn('Another install or update is running; this one will start when it finishes.', out)
        self.assertNotIn('package database locked', out)
        self.assertEqual(self.log('xbps.log')[0], '-S')      # synced only after the wait
        self.assertIn('-y maim', self.installs())

    def test_menu_warns_before_opening_the_terminal_when_busy(self):
        self.write('busy', '5')
        self.software('--install', 'maim')
        self.assertIn('-a Abyss Another install or update is running This one will start when it finishes.',
                      self.log('notify.log'))
        self.assertEqual(len(self.log('setsid.log')), 1)

    # Sync retry -------------------------------------------------------------
    def test_sync_is_retried_after_a_transient_dns_failure(self):
        self.write('sync-fail', '1')
        self.write('sync-error', "ERROR: [reposync] failed to fetch file `https://mrzakaria.github.io/"
                                 "AbyssLinuxPMR/current/aarch64-repodata': Transient resolver failure\n")
        out = self.software('--run-install', '--yes', 'maim')
        self.assertEqual(self.status, 0, out)
        self.assertEqual(self.log('xbps.log').count('-S'), 2)
        self.assertIn('trying again', out)
        self.assertNotIn('could not be updated', out)
        self.assertIn('-y maim', self.installs())

    def test_persistent_dns_failure_is_explained(self):
        self.write('sync-fail', '9')
        self.write('sync-error', "ERROR: [reposync] failed to fetch file `x': Transient resolver failure\n")
        out = self.software('--run-install', '--yes', 'maim')
        self.assertEqual(self.log('xbps.log').count('-S'), 3)
        self.assertIn('cannot look', out)
        self.assertIn('(DNS)', out)
        self.assertIn('run "update"', out)
        self.assertIn('Continuing with the package lists already on this computer.', out)
        self.assertIn('may be out of date', out)

    def test_password_is_asked_once_and_a_refusal_is_explained(self):
        # abyss-priv only prompts when not root; it marks what it runs as root.
        # (doas too: the script puts /usr/local/bin first, where a real
        # abyss-priv may exist and call doas.)
        for tool in ('abyss-priv', 'doas'):
            self.stub(tool, '[ -n "$FAKE_ROOT" ] || echo "prompt: $*" >> "$HOME/priv.log"\n'
                            'FAKE_ROOT=1 exec "$@"')
        self.stub('id', '[ "$1" = -u ] && [ -n "$FAKE_ROOT" ] && { echo 0; exit; }; echo 1000')
        out = self.software('--run-install', '--yes', 'maim')
        self.assertEqual(self.status, 0, out)
        prompts = self.log('priv.log')
        self.assertEqual(len(prompts), 1, prompts)           # one password for sync + install
        self.assertRegex(prompts[0], r'--run-install --elevated \S+ --yes maim$')
        self.assertIn('-y maim', self.installs())

        for tool in ('abyss-priv', 'doas'):
            self.stub(tool, 'echo "doas: Authentication failed" >&2; exit 1')
        out = self.software('--run-install', '--yes', 'maim')
        self.assertNotEqual(self.status, 0)
        self.assertIn('needs your password', out)
        self.assertNotIn('trying again', out)
        self.assertEqual(list(self.root.glob('abyss-elevate.*')), [])

    # Package lists synced moments ago are not downloaded again ---------------
    def syncs(self):
        return self.log('xbps.log').count('-S')

    def test_second_install_reuses_lists_synced_moments_ago(self):
        self.software('--run-install', '--yes', 'maim')
        self.assertEqual(self.syncs(), 1)
        self.assertTrue((self.root / 'synced').exists())
        out = self.software('--run-install', '--yes', 'vlc')
        self.assertEqual(self.status, 0, out)
        self.assertEqual(self.syncs(), 1, out)                # no second download
        self.assertIn('Package lists are up to date (updated less than 30 minutes ago).', out)
        self.assertIn('-y vlc', self.installs())

    def test_stale_lists_are_synced_again(self):
        self.software('--run-install', '--yes', 'maim')
        os.utime(self.root / 'synced', (0, 0))                # synced long ago
        out = self.software('--run-install', '--yes', 'vlc')
        self.assertEqual(self.syncs(), 2, out)
        self.assertNotIn('up to date', out)

    def test_freshness_window_can_be_changed(self):
        self.software('--run-install', '--yes', 'maim')
        out = self.software('--run-install', '--yes', 'vlc', env={'ABYSS_SYNC_FRESH_MIN': '0'})
        self.assertEqual(self.syncs(), 2, out)

    def test_repository_without_lists_forces_a_sync(self):
        self.software('--run-install', '--yes', 'maim')
        self.write('repos', '   8 https://repo-default.voidlinux.org/current/aarch64 (RSA signed)\n'
                            '  -1 https://repo-default.voidlinux.org/current/aarch64/nonfree (RSA maybe-signed)\n')
        out = self.software('--run-install', '--yes', 'vlc')
        self.assertEqual(self.syncs(), 2, out)

    def test_failed_sync_is_not_remembered_and_is_retried_next_time(self):
        self.write('sync-fail', '3')
        self.write('sync-error', "ERROR: [reposync] failed to fetch file `x': Transient resolver failure\n")
        self.software('--run-install', '--yes', 'maim')
        self.assertEqual(self.syncs(), 3)
        self.assertFalse((self.root / 'synced').exists())
        out = self.software('--run-install', '--yes', 'vlc')
        self.assertEqual(self.syncs(), 4, out)               # synced (and retried) again
        self.assertNotIn('up to date', out)

    def test_update_always_syncs(self):
        self.software('--run-install', '--yes', 'maim')
        out = self.software('--run-install', '--yes', '--update', 'firefox')
        self.assertEqual(self.syncs(), 2, out)

    # Missing packages -------------------------------------------------------
    def test_missing_package_is_named_and_the_rest_is_installed(self):
        self.write('missing', 'thunar\npipewire-pulse\n')
        out = self.software('--run-install', '--yes', 'udisks2', 'thunar', 'gvfs', 'pipewire-pulse')
        self.assertEqual(self.status, 1)
        self.assertIn('-y udisks2 gvfs', self.installs())
        self.assertIn('Installed: udisks2 gvfs', out)
        self.assertIn('Not available for aarch64 in the enabled repositories: thunar pipewire-pulse', out)

    def test_unresolvable_dependency_is_named(self):
        self.write('broken', 'docker\n')
        out = self.software('--run-install', '--yes', 'docker', 'vlc')
        self.assertEqual(self.status, 1)
        self.assertIn('-y vlc', self.installs())
        self.assertIn('Cannot be installed on this system (dependency problem): docker', out)

    def test_nothing_available_installs_nothing(self):
        self.write('missing', 'ghost\n')
        out = self.software('--run-install', '--yes', 'ghost')
        self.assertEqual(self.status, 1)
        self.assertEqual(self.installs(), [])
        self.assertIn('Nothing was installed.', out)

    def test_failed_install_is_reported(self):
        self.write('install-fail', '')
        out = self.software('--run-install', '--yes', 'maim')
        self.assertEqual(self.status, 1)
        self.assertIn('Not installed: maim (xbps-install exit 1; see the messages above)', out)

    def test_declining_at_the_xbps_prompt_is_not_reported_as_installed(self):
        self.write('decline', '')
        out = self.software('--run-install', 'maim')
        self.assertEqual(self.status, 1)
        self.assertIn('Not installed (cancelled): maim', out)
        self.assertNotIn('Installed:', out)

    # Download size -------------------------------------------------------------
    def test_large_bundle_states_its_size_and_can_be_cancelled(self):
        self.write('size', str(950 * 1024 * 1024))           # 2 packages -> about 1.9 GB
        self.write('dmenu.answers', 'Cancel\n')
        self.software('--install', 'texlive zathura')
        prompt = self.log('dmenu.log')
        self.assertIn('## -i -c -l 13 -fn JetBrainsMono Nerd Font:size=10 -nb #0d0b18 -nf #f3e8ff '
                      '-sb #a855f7 -sf #090514 -p Large download', prompt)
        self.assertIn('Install (downloads 1.9 GB, needs 4 KB of disk)', prompt)
        self.assertEqual(self.log('setsid.log'), [])

        self.write('dmenu.answers', 'Install (downloads 1.9 GB, needs 4 KB of disk)\n')
        self.software('--install', 'texlive zathura')
        self.assertEqual(len(self.log('setsid.log')), 1)

    def test_small_bundle_does_not_ask(self):
        self.software('--install', 'maim')
        self.assertEqual(self.log('dmenu.log'), [])
        self.assertIn(f"st -t Install software -e sh -c /bin/sh '{SOFTWARE}' --run-install maim",
                      self.log('setsid.log')[0])

    def test_rejects_names_that_are_not_package_names(self):
        self.software('--install', 'maim; rm -rf ~')
        self.assertEqual(self.log('setsid.log'), [])

    # Several packages in one --install argument (abyss-control-center) ------
    def test_install_audio_checks_each_package_separately(self):
        names = re.search(r"install-audio\).*--install '([^']+)'", CENTER.read_text()).group(1)
        self.assertEqual(names, 'pipewire wireplumber pavucontrol')   # pulse server is in pipewire
        self.software('--install', names)
        self.assertRegex(self.log('setsid.log')[0], r"--run-install pipewire wireplumber pavucontrol;")
        self.software('--run-install', '--yes', *names.split())
        self.assertEqual(self.status, 0, self.output)
        self.assertEqual([q for q in self.log('query.log') if q.startswith('-R')],
                         ['-R pipewire', '-R wireplumber', '-R pavucontrol'])
        self.assertIn('-y pipewire wireplumber pavucontrol', self.installs())

    # Installed state in the menu ----------------------------------------------
    def menu(self, *answers):
        self.write('catalog', 'Firefox (Void package)\tpkg:firefox\n'
                              'Media tools\tpkg:mpv yt-dlp ffmpeg\n'
                              'Bluetooth support\tpkg:bluez\n')
        self.write('dmenu.answers', ''.join(a + '\n' for a in answers))
        return self.software(env={'ABYSS_SOFTWARE_CATALOG': str(self.root / 'catalog'),
                                  'ABYSS_APPLICATIONS_DIR': str(self.root / 'applications')})

    def menu_listing(self):
        lines = self.log('dmenu.log')
        start = lines.index(next(l for l in lines if l.endswith('-p Software (type to filter)')))
        return lines[start + 1:start + 4]

    def test_menu_marks_installed_and_partly_installed_bundles(self):
        self.write('installed', 'firefox\nmpv\nlibfoo\n')
        self.menu()
        self.assertEqual(self.menu_listing(), [
            'Firefox (Void package)  ✓ installed',
            'Media tools  (partly installed, missing: yt-dlp ffmpeg)',
            'Bluetooth support'])
        self.assertEqual([q for q in self.log('query.log') if q == '-l'], ['-l'])   # one local query

    def test_installed_bundle_offers_open_update_and_remove(self):
        self.write('installed', 'firefox\n')
        (self.root / 'applications').mkdir()
        self.write('applications/firefox.desktop', '')
        self.stub('firefox', 'exit 0')
        self.menu('Firefox (Void package)  ✓ installed', 'Update')
        self.assertIn('Open firefox', self.log('dmenu.log'))
        self.assertIn('Remove', self.log('dmenu.log'))
        self.assertRegex(self.log('setsid.log')[0], r"--run-install --update firefox;")

    def test_installed_bundle_can_be_removed_after_confirmation(self):
        self.write('installed', 'bluez\n')
        self.menu('Bluetooth support  ✓ installed', 'Remove', 'Remove bluez')
        self.assertNotIn('Open bluez', self.log('dmenu.log'))
        self.assertRegex(self.log('setsid.log')[0], r"--run-remove bluez;")
        out = self.software('--run-remove', 'bluez')
        self.assertEqual(self.status, 0, out)
        self.assertIn('remove -R bluez', self.log('xbps.log'))
        self.assertIn('Removed: bluez', out)

    def test_partly_installed_bundle_installs_only_the_missing_parts(self):
        self.write('installed', 'mpv\n')
        self.menu('Media tools  (partly installed, missing: yt-dlp ffmpeg)', 'Install missing: yt-dlp ffmpeg')
        self.assertIn('Remove installed parts: mpv', self.log('dmenu.log'))
        self.assertRegex(self.log('setsid.log')[0], r"--run-install yt-dlp ffmpeg;")

    def test_update_mode_updates_instead_of_installing(self):
        out = self.software('--run-install', '--yes', '--update', 'firefox')
        self.assertEqual(self.status, 0, out)
        self.assertIn('-y -u firefox', self.installs())
        self.assertIn('Up to date: firefox', out)

    # Package search ----------------------------------------------------------
    def test_search_keeps_dashes_and_digits_in_package_names(self):
        self.stub('xbps-query', r'''printf '%s\n' \
            '[-] font-adobe-100dpi-1.0.4_1            Standard 100dpi Adobe PCF fonts' \
            '[-] lf-r42_2                             Terminal file manager' \
            '[*] python3-3.13.9_1                     Python programming language' ''')
        self.write('dmenu.answers', 'adobe\n')
        self.software('--search')
        listing = self.log('dmenu.log')
        self.assertIn('font-adobe-100dpi — Standard 100dpi Adobe PCF fonts', listing)
        self.assertIn('lf — Terminal file manager', listing)
        self.assertIn('python3 — Python programming language', listing)


@unittest.skipUnless(Path(PROFILE).is_file(), 'abyss-desktop shell helpers (zz-abyss-cli.sh) not found; set ABYSS_PROFILE')
class ShellHelpersTest(StubbedTest):
    """update/upgrade/install from /etc/profile.d (interactive bash only)."""

    def shell(self, code):
        result = subprocess.run(['bash', '--norc', '--noprofile', '-i', '-c', f'. "{PROFILE}"; {code}'],
                                env={**self.env, 'PS1': '$ '}, cwd=self.root, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, timeout=60)
        self.status, self.output = result.returncode, result.stdout
        return result.stdout

    def test_update_waits_and_retries(self):
        self.write('busy', '2')
        self.write('sync-fail', '1')
        self.write('sync-error', "ERROR: [reposync] failed to fetch file `x': Transient resolver failure\n")
        out = self.shell('update')
        self.assertEqual(self.status, 0, out)
        self.assertIn('Another install or update is running; this one will start when it finishes.', out)
        self.assertEqual(self.log('xbps.log'), ['-S', '-S'])

    def test_update_explains_a_dns_failure(self):
        self.write('sync-fail', '9')
        self.write('sync-error', "ERROR: [reposync] failed to fetch file `x': Transient resolver failure\n")
        out = self.shell('update')
        self.assertEqual(self.status, 1)
        self.assertIn('could not be found (DNS)', out)
        self.assertEqual(self.log('xbps.log').count('-S'), 3)

    def test_upgrade_and_install_sync_first(self):
        self.shell('upgrade; install maim')
        self.assertEqual(self.log('xbps.log'), ['-S', '-u', '-S', 'maim'])


if __name__ == '__main__':
    unittest.main()
