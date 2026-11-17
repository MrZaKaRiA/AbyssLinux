"""Check the wallpaper manager and the wallpaper helper without an X server."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / 'custom-overlay/usr/local/bin'
MANAGER = Path(os.environ.get('ABYSS_WALLPAPERS', BIN / 'abyss-wallpapers')).resolve()
HELPER = Path(os.environ.get('ABYSS_WALLPAPER', BIN / 'abyss-wallpaper')).resolve()
CENTER = Path(os.environ.get('ABYSS_CENTER', BIN / 'abyss-control-center')).resolve()

# Only these programs exist for the scripts, so an installed zenity, nsxiv or
# feh on the machine running the tests can never be picked up by accident.
TOOLS = ('sh awk sed head tail cat cp rm mv mkdir cmp tr cut sort find grep id sleep pgrep '
         'dirname basename chmod env').split()

DMENU = '''{ echo "## $*"; cat; } >> "$HOME/dmenu.log"
a="$HOME/dmenu.answers"
[ -s "$a" ] || exit 1
head -n 1 "$a"
tail -n +2 "$a" > "$a.new"; mv "$a.new" "$a"'''
# Pictures made by the tests start with IMG; anything else is "text".
FILE = '''for f; do :; done
case "$(head -c 3 "$f")" in IMG) echo image/png ;; *) echo text/plain ;; esac'''


class WallpaperTest(unittest.TestCase):
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
        self.stub('feh', '''printf '%s\\n' "$*" >> "$HOME/feh.log"''')
        self.stub('xsetroot', '''printf '%s\\n' "$*" >> "$HOME/xsetroot.log"''')
        self.stub('abyss-wallpaper', f'exec /bin/sh "{HELPER}" "$@"')
        self.stub('dmenu', DMENU)
        self.stub('notify-send', '''printf '%s\\n' "$*" >> "$HOME/notify.log"''')
        self.stub('file', FILE)
        self.system = self.root / 'system'
        self.system.mkdir()
        self.default = self.image(self.system / 'abyss-wallpaper.jpg')
        self.orbit = self.image(self.system / 'abyss-orbit.jpg')
        self.image(self.system / 'abyss-splash.png')
        self.user = self.root / '.local/share/backgrounds'
        self.choice = self.root / '.config/abyss/wallpaper'
        self.mode = self.root / '.config/abyss/wallpaper-mode'
        self.env = {'HOME': str(self.root), 'PATH': str(self.bin), 'ABYSS_BACKGROUNDS_DIR': str(self.system)}

    def stub(self, name, body):
        path = self.bin / name
        if path.is_symlink():
            path.unlink()          # never write through a link to the real tool
        path.write_text('#!/bin/sh\n' + body + '\n')
        path.chmod(0o755)

    def image(self, path, content='IMG'):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def log(self, name):
        path = self.root / name
        return path.read_text().splitlines() if path.exists() else []

    def run_script(self, script, *args, cwd=None):
        result = subprocess.run(['/bin/sh', str(script), *args], env=self.env, cwd=cwd or self.root,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.status, self.output, self.errors = result.returncode, result.stdout, result.stderr
        return result.stdout

    def manager(self, *args, **kw):
        return self.run_script(MANAGER, *args, **kw)

    def ok(self, *args, **kw):
        out = self.manager(*args, **kw)
        self.assertEqual(self.status, 0, self.errors)
        return out

    def rows(self):
        return [line.split('\t') for line in self.ok('list').splitlines()]

    def menu(self, *answers):
        (self.root / 'dmenu.answers').write_text(''.join(a + '\n' for a in answers))
        self.manager()
        return self.log('dmenu.log')

    def prompts(self):
        """The dmenu calls so far: [prompt, row, row, ...] for each."""
        calls = []
        for line in self.log('dmenu.log'):
            if line.startswith('## '):
                calls.append([line.split(' -p ', 1)[1]])
            else:
                calls[-1].append(line)
        return calls

    # ---- list ----------------------------------------------------------------
    def test_list_shows_system_then_user_with_friendly_names(self):
        self.image(self.system / 'abyss-deep_sea.png')
        self.image(self.system / 'notes.txt')
        self.image(self.user / 'my holiday-photo.JPG')
        self.image(self.user / 'cat.webp')
        self.assertEqual(self.rows(), [
            [str(self.default), 'Abyss (galaxy)', 'system', 'current'],
            [str(self.system / 'abyss-deep_sea.png'), 'Deep sea', 'system', '-'],
            [str(self.orbit), 'Orbit (light trails)', 'system', '-'],
            [str(self.user / 'cat.webp'), 'Cat', 'user', '-'],
            [str(self.user / 'my holiday-photo.JPG'), 'My holiday photo', 'user', '-'],
        ])
        self.assertNotIn('splash', self.output)

    def test_list_without_user_directory_and_same_labels(self):
        self.assertEqual([r[1] for r in self.rows()], ['Abyss (galaxy)', 'Orbit (light trails)'])
        self.image(self.user / 'sky.jpg')
        self.image(self.user / 'sky.png')
        self.assertEqual([r[1] for r in self.rows()][2:], ['Sky', 'Sky (sky.png)'])

    def test_user_folder_exists_once_the_manager_has_looked(self):
        # Users were told to drop images into ~/.local/share/backgrounds, but
        # only the first "add" created it.
        self.assertFalse(self.user.exists())
        self.rows()
        self.assertTrue(self.user.is_dir())
        self.image(self.user / 'copied by hand.png')
        self.assertIn('Copied by hand', [r[1] for r in self.rows()])
        self.ok('set', 'copied by hand')
        self.assertEqual(self.choice.read_text(), f'{self.user}/copied by hand.png\n')

    # ---- set -----------------------------------------------------------------
    def test_set_by_name(self):
        self.ok('set', 'orbit')
        self.assertEqual(self.choice.read_text(), f'{self.orbit}\n')
        self.assertEqual(self.log('feh.log'), [f'--no-fehbg --bg-fill {self.orbit}'])
        self.assertEqual([r[3] for r in self.rows()], ['-', 'current'])
        for name in ('abyss-orbit.jpg', 'abyss-orbit', 'Orbit (light trails)'):
            self.choice.unlink()
            self.ok('set', name)
            self.assertEqual(self.choice.read_text(), f'{self.orbit}\n')

    def test_set_by_path_with_spaces(self):
        photo = self.image(self.root / 'My Photos/sun set.png')
        self.ok('set', str(photo))
        self.assertEqual(self.choice.read_text(), f'{photo}\n')
        self.assertEqual(self.log('feh.log')[-1], f'--no-fehbg --bg-fill {photo}')
        self.assertIn([str(photo), 'Sun set', 'other', 'current'], self.rows())
        self.ok('set', 'sun set.png', cwd=photo.parent)
        self.assertEqual(self.choice.read_text(), f'{photo}\n')
        self.ok('set', '~/My Photos/sun set.png')
        self.assertEqual(self.choice.read_text(), f'{photo}\n')

    def test_set_none_and_default(self):
        self.ok('set', 'none')
        self.assertEqual(self.choice.read_text(), 'none\n')
        self.assertEqual(self.log('feh.log'), [])
        self.assertEqual(self.log('xsetroot.log'), ['-solid #000000'])
        self.assertEqual([r[3] for r in self.rows()], ['-', '-'])
        self.ok('set', 'default')
        self.assertFalse(self.choice.exists())
        self.assertEqual(self.log('feh.log'), [f'--no-fehbg --bg-fill {self.default}'])
        self.ok('set', 'orbit')
        self.ok('set', 'Abyss (galaxy)')
        self.assertFalse(self.choice.exists())

    def test_set_rejects_unknown_names_and_non_images(self):
        self.ok('set', 'orbit')
        notes = self.image(self.root / 'notes.txt')
        fake = self.image(self.root / 'fake.jpg', 'just text')
        for bad in ('nothing-like-this', str(notes), str(fake), str(self.root / 'missing.png'), ''):
            self.manager('set', bad)
            self.assertNotEqual(self.status, 0, bad)
            self.assertTrue(self.errors.strip(), bad)
        self.assertEqual(self.choice.read_text(), f'{self.orbit}\n')
        self.assertEqual(len(self.log('feh.log')), 1)

    # ---- add -----------------------------------------------------------------
    def test_add_copies_and_applies(self):
        photo = self.image(self.root / 'Downloads/beach.jpg', 'IMG beach')
        self.ok('add', str(photo))
        copy = self.user / 'beach.jpg'
        self.assertEqual(copy.read_text(), 'IMG beach')
        self.assertTrue(photo.exists())
        self.assertEqual(self.choice.read_text(), f'{copy}\n')
        self.assertEqual(self.log('feh.log'), [f'--no-fehbg --bg-fill {copy}'])
        self.assertIn([str(copy), 'Beach', 'user', 'current'], self.rows())

    def test_add_never_overwrites_another_picture(self):
        first = self.image(self.root / 'a/beach.jpg', 'IMG one')
        second = self.image(self.root / 'b/beach.jpg', 'IMG two')
        third = self.image(self.root / 'c/beach.jpg', 'IMG three')
        for photo in (first, second, third, second):
            self.ok('add', str(photo))
        self.assertEqual(sorted(p.name for p in self.user.iterdir()), ['beach-1.jpg', 'beach-2.jpg', 'beach.jpg'])
        self.assertEqual((self.user / 'beach.jpg').read_text(), 'IMG one')
        self.assertEqual((self.user / 'beach-1.jpg').read_text(), 'IMG two')
        self.assertEqual((self.user / 'beach-2.jpg').read_text(), 'IMG three')
        # the same picture again is used as it is, not copied a second time
        self.assertEqual(self.choice.read_text(), f"{self.user / 'beach-1.jpg'}\n")

    def test_add_handles_spaces(self):
        photo = self.image(self.root / 'My Pictures/New York (night).png')
        self.ok('add', str(photo))
        copy = self.user / 'New York (night).png'
        self.assertTrue(copy.exists())
        self.assertEqual(self.choice.read_text(), f'{copy}\n')
        self.assertEqual(self.log('feh.log'), [f'--no-fehbg --bg-fill {copy}'])
        self.image(self.root / 'My Pictures/New York (night).png', 'IMG other')
        self.ok('add', str(photo))
        self.assertTrue((self.user / 'New York (night)-1.png').exists())

    def test_add_an_image_that_is_already_mine(self):
        mine = self.image(self.user / 'mine.png')
        self.ok('add', str(mine))
        self.assertEqual([p.name for p in self.user.iterdir()], ['mine.png'])
        self.assertEqual(self.choice.read_text(), f'{mine}\n')

    def test_add_rejects_what_is_not_an_image(self):
        for bad in (self.image(self.root / 'notes.txt'), self.image(self.root / 'script.jpg', '#!/bin/sh\n'),
                    self.root / 'missing.jpg', self.root):
            self.manager('add', str(bad))
            self.assertNotEqual(self.status, 0, bad)
            self.assertTrue(self.errors.strip(), bad)
        self.assertFalse(self.user.exists() and list(self.user.iterdir()))
        self.assertFalse(self.choice.exists())
        self.assertEqual(self.log('feh.log'), [])

    def test_add_without_file_installed_trusts_the_extension(self):
        (self.bin / 'file').unlink()
        self.ok('add', str(self.image(self.root / 'photo.jpeg', 'whatever')))
        self.assertTrue((self.user / 'photo.jpeg').exists())
        self.manager('add', str(self.image(self.root / 'notes.txt')))
        self.assertNotEqual(self.status, 0)

    # ---- remove --------------------------------------------------------------
    def test_remove_current_falls_back_to_default(self):
        mine = self.image(self.user / 'my cat.png')
        self.ok('set', 'my cat')
        self.assertEqual(self.choice.read_text(), f'{mine}\n')
        self.ok('remove', 'my cat.png')
        self.assertFalse(mine.exists())
        self.assertFalse(self.choice.exists())
        self.assertEqual(self.log('feh.log')[-1], f'--no-fehbg --bg-fill {self.default}')
        self.assertEqual([r[3] for r in self.rows()], ['current', '-'])

    def test_remove_another_image_keeps_the_choice(self):
        mine = self.image(self.user / 'cat.png')
        self.ok('set', 'orbit')
        self.ok('remove', 'Cat')
        self.assertFalse(mine.exists())
        self.assertEqual(self.choice.read_text(), f'{self.orbit}\n')
        self.assertEqual(len(self.log('feh.log')), 1)

    def test_remove_only_touches_user_images(self):
        outside = self.image(self.root / 'elsewhere/keep.png')
        self.ok('set', str(outside))
        for name in ('orbit', 'abyss-orbit.jpg', str(self.orbit), str(outside), 'keep', '../../elsewhere/keep.png', ''):
            self.manager('remove', name)
            self.assertNotEqual(self.status, 0, name)
        self.assertTrue(self.orbit.exists() and outside.exists() and self.default.exists())

    # ---- mode ----------------------------------------------------------------
    def test_mode_persists_and_picks_the_feh_flag(self):
        self.assertEqual(self.ok('mode').strip(), 'fill')
        self.ok('set', 'orbit')
        flags = {'fit': '--bg-max', 'center': '--bg-center', 'tile': '--bg-tile', 'fill': '--bg-fill'}
        for mode, flag in flags.items():
            self.ok('mode', mode)
            self.assertEqual(self.mode.read_text(), f'{mode}\n')
            self.assertEqual(self.log('feh.log')[-1], f'--no-fehbg {flag} {self.orbit}')
            self.assertEqual(self.ok('mode').strip(), mode)
        self.ok('mode', 'tile')
        self.ok('set', 'default')          # the mode survives another choice
        self.assertEqual(self.log('feh.log')[-1], f'--no-fehbg --bg-tile {self.default}')
        self.run_script(HELPER)            # ... and the next login
        self.assertEqual(self.log('feh.log')[-1], f'--no-fehbg --bg-tile {self.default}')
        self.assertEqual(self.choice.exists(), False)

    def test_bad_mode_is_refused(self):
        self.ok('mode', 'fit')
        self.manager('mode', 'stretch')
        self.assertNotEqual(self.status, 0)
        self.assertEqual(self.mode.read_text(), 'fit\n')
        self.mode.write_text('nonsense\n')
        self.run_script(HELPER)
        self.assertEqual(self.log('feh.log')[-1], f'--no-fehbg --bg-fill {self.default}')

    # ---- the helper and the one-line choice file -----------------------------
    def test_choice_file_from_the_old_menu_still_works(self):
        self.run_script(HELPER, 'none')            # old "Wallpaper: black (OLED)"
        self.assertEqual(self.choice.read_text(), 'none\n')
        self.assertEqual(self.log('xsetroot.log'), ['-solid #000000'])
        self.assertEqual([r[3] for r in self.rows()], ['-', '-'])
        self.run_script(HELPER, 'abyss')           # old "Wallpaper: Abyss"
        self.assertFalse(self.choice.exists())
        self.assertEqual(self.log('feh.log'), [f'--no-fehbg --bg-fill {self.default}'])
        self.assertEqual(self.rows()[0][3], 'current')
        photo = self.image(self.root / 'Pictures/own.png')
        self.choice.write_text('~/Pictures/own.png\n')   # written by hand
        self.run_script(HELPER)
        self.assertEqual(self.log('feh.log')[-1], f'--no-fehbg --bg-fill {photo}')
        self.assertIn([str(photo), 'Own', 'other', 'current'], self.rows())
        self.choice.write_text('/gone/away.png\n')
        self.run_script(HELPER)
        self.assertEqual(self.log('feh.log')[-1], f'--no-fehbg --bg-fill {self.default}')
        self.assertEqual(self.rows()[0][3], 'current')

    def test_manager_keeps_the_choice_file_one_line(self):
        self.ok('set', 'orbit')
        self.ok('mode', 'fit')
        self.assertEqual(self.choice.read_text(), f'{self.orbit}\n')

    def test_legacy_login_leaves_the_default_to_an_old_xinitrc(self):
        self.stub('pgrep', 'case "$*" in *dwm*) exit 0 ;; esac; exit 1')
        self.stub('sleep', ':')
        (self.root / '.xinitrc').write_text('feh --bg-fill /usr/share/backgrounds/abyss/abyss-wallpaper.jpg &\n')
        del self.env['ABYSS_BACKGROUNDS_DIR']     # the old file names the real path
        self.run_script(HELPER, '--legacy')
        self.assertEqual(self.log('feh.log'), [])
        self.assertEqual(self.log('xsetroot.log'), [])
        self.choice.parent.mkdir(parents=True, exist_ok=True)
        self.choice.write_text(f'{self.orbit}\n')
        self.run_script(HELPER, '--legacy')
        self.assertEqual(self.log('feh.log'), [f'--no-fehbg --bg-fill {self.orbit}'])

    # ---- menu ----------------------------------------------------------------
    def test_menu_rows_and_choosing(self):
        self.image(self.user / 'cat.png')
        log = self.menu('Orbit (light trails)', 'Black (OLED)')
        self.assertEqual(self.prompts()[0], ['Wallpaper', 'Abyss (galaxy)  (current)', 'Orbit (light trails)', 'Cat', 'Black (OLED)',
                                 'Add an image…', 'Fit: Fill the screen (edges may be cropped)…',
                                 'Remove one of my images…', 'Close'])
        self.assertIn('Orbit (light trails)  (current)', log)
        self.assertIn('Black (OLED)  (current)', log)
        self.assertEqual(self.choice.read_text(), 'none\n')
        self.assertEqual(self.log('feh.log'), [f'--no-fehbg --bg-fill {self.orbit}'])
        self.assertEqual(self.status, 0)
        self.assertEqual(self.log('notify.log'), [])

    def test_menu_current_row_can_be_chosen_and_close_ends(self):
        log = self.menu('Abyss (galaxy)  (current)', 'Close', 'Orbit (light trails)')
        self.assertEqual(self.log('feh.log'), [f'--no-fehbg --bg-fill {self.default}'])
        self.assertNotIn('Remove one of my images…', log)
        self.assertNotIn('Preview wallpapers… (m marks one, q closes)', log)

    def test_menu_fit(self):
        log = self.menu('Fit: Fill the screen (edges may be cropped)…', 'Tile (repeat)')
        self.assertEqual(self.mode.read_text(), 'tile\n')
        self.assertEqual(self.log('feh.log'), [f'--no-fehbg --bg-tile {self.default}'])
        self.assertIn('Fill the screen (edges may be cropped)  (current)', log)
        self.assertIn('Fit: Tile (repeat)…', log)

    def test_menu_add_with_zenity(self):
        photo = self.image(self.root / 'Downloads/new one.png')
        self.stub('zenity', f'''printf '%s\\n' "$*" >> "$HOME/zenity.log"; echo "{photo}"''')
        self.menu('Add an image…')
        copy = self.user / 'new one.png'
        self.assertTrue(copy.exists())
        self.assertEqual(self.choice.read_text(), f'{copy}\n')
        self.assertIn('--file-selection', self.log('zenity.log')[0])
        self.assertIn('--file-filter=Images | *.jpg', self.log('zenity.log')[0])

    def test_menu_add_cancelled_or_wrong_file(self):
        self.stub('zenity', 'exit 1')
        self.menu('Add an image…')
        self.assertFalse(self.choice.exists())
        self.assertEqual(self.log('notify.log'), [])
        notes = self.image(self.root / 'notes.txt')
        self.stub('zenity', f'echo "{notes}"')
        self.menu('Add an image…')
        self.assertFalse(self.choice.exists())
        self.assertEqual(len(self.log('notify.log')), 1)
        self.assertIn('Not an image', self.log('notify.log')[0])

    def test_menu_add_with_nsxiv_over_pictures(self):
        self.image(self.root / 'Pictures/2026/b trip.jpg')
        self.image(self.root / 'Pictures/a.png')
        self.image(self.root / 'Pictures/readme.txt')
        self.stub('nsxiv', '''printf '%s\\n' "$*" >> "$HOME/nsxiv.log"; cat > "$HOME/nsxiv.in"; head -n 1 "$HOME/nsxiv.in"''')
        self.menu('Add an image…', 'OK')
        self.assertEqual(self.log('nsxiv.log'), ['-t -o -i'])
        self.assertEqual(self.log('nsxiv.in'), [str(self.root / 'Pictures/2026/b trip.jpg'), str(self.root / 'Pictures/a.png')])
        self.assertEqual(self.choice.read_text(), f"{self.user / 'b trip.jpg'}\n")

    def test_menu_add_by_typing_a_path(self):
        self.image(self.root / 'Downloads/typed image.webp')
        self.stub('nsxiv', 'exit 1')        # installed, but ~/Pictures has no images
        self.menu('Add an image…', '~/Downloads/typed image.webp')
        self.assertEqual(self.prompts()[1], ['Image file (type or paste a path):'])
        self.assertEqual(self.choice.read_text(), f"{self.user / 'typed image.webp'}\n")

    def test_menu_preview(self):
        self.image(self.user / 'cat.png')
        self.stub('nsxiv', '''cat > "$HOME/nsxiv.in"; sed -n 2p "$HOME/nsxiv.in"''')
        log = self.menu('Preview wallpapers… (m marks one, q closes)')
        self.assertIn('Preview wallpapers… (m marks one, q closes)', log)
        self.assertEqual(self.log('nsxiv.in'), [str(self.default), str(self.orbit), str(self.user / 'cat.png')])
        self.assertEqual(self.choice.read_text(), f'{self.orbit}\n')
        self.stub('nsxiv', 'cat > /dev/null')      # nothing marked: nothing changes
        self.menu('Preview wallpapers… (m marks one, q closes)')
        self.assertEqual(self.choice.read_text(), f'{self.orbit}\n')
        self.assertEqual(len(self.log('feh.log')), 1)

    def test_menu_remove(self):
        cat = self.image(self.user / 'cat.png')
        dog = self.image(self.user / 'dog.png')
        self.ok('set', 'dog')
        self.menu('Remove one of my images…', 'Dog  (current)')
        self.assertEqual(self.prompts()[1], ['Delete which image?', 'Cat', 'Dog  (current)'])
        self.assertNotIn('Dog  (current)', self.prompts()[2])
        self.assertTrue(cat.exists())
        self.assertFalse(dog.exists())
        self.assertFalse(self.choice.exists())
        self.assertEqual(self.log('feh.log')[-1], f'--no-fehbg --bg-fill {self.default}')

    def test_messages_without_notify_send_use_dmenu(self):
        (self.bin / 'notify-send').unlink()
        notes = self.image(self.root / 'notes.txt')
        self.stub('zenity', f'echo "{notes}"')
        self.menu('Add an image…')
        self.assertIn('Not an image', self.prompts()[1][0])
        self.assertEqual(self.prompts()[1][1:], ['OK'])

    # ---- control center ------------------------------------------------------
    def test_control_center_has_one_wallpaper_row(self):
        text = CENTER.read_text()
        self.assertIn('Wallpaper…\twallpapers\n', text)
        self.assertNotIn('Wallpaper: ', text)
        self.assertIn('wallpapers)   if has abyss-wallpapers; then abyss-wallpapers', text)
        self.assertIn('wallpaper)    abyss-wallpaper ;;', text)
        self.assertIn('wallpaper-abyss|wallpaper-none) abyss-wallpaper "${1#wallpaper-}" ;;', text)


if __name__ == '__main__':
    unittest.main()
