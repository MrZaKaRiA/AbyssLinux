#!/usr/bin/env python3
"""Check img argument handling and the Images application entry."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
IMG = Path(os.environ.get('ABYSS_IMG', ROOT / 'custom-overlay/usr/bin/img'))
APPS = Path(os.environ.get('ABYSS_APPS', ROOT / 'custom-overlay/usr/local/bin/abyss-apps'))
DESKTOP = Path(os.environ.get('ABYSS_IMAGES_DESKTOP', ROOT / 'custom-overlay/usr/share/applications/abyss-images.desktop'))

MOCK = '''#!/usr/bin/env python3
import json, os, sys
with open(os.environ['ABYSS_IMAGE_LOG'], 'w') as out:
    json.dump([os.path.basename(sys.argv[0])] + sys.argv[1:], out)
'''

class ImageLauncherTest(unittest.TestCase):
    def test_img_preserves_file_arguments_and_opens_pictures_without_args(self):
        with tempfile.TemporaryDirectory(prefix='abyss-img-test-') as tmp:
            root = Path(tmp)
            bindir = root / 'bin'
            bindir.mkdir()
            for name in ('nsxiv', 'abyss-control-center'):
                path = bindir / name
                path.write_text(MOCK)
                path.chmod(0o755)
            log = root / 'args.json'
            env = os.environ.copy()
            env.update(PATH=f'{bindir}:/usr/bin:/bin', ABYSS_IMAGE_LOG=str(log))
            image = str(root / 'photo with spaces.png')
            subprocess.run([str(IMG), '-t', image], env=env, check=True, timeout=5)
            self.assertEqual(json.loads(log.read_text()), ['nsxiv', '-t', image])
            subprocess.run([str(IMG)], env=env, check=True, timeout=5)
            self.assertEqual(json.loads(log.read_text()), ['abyss-control-center', 'images'])

    def test_images_entry_is_listed_even_though_stock_nsxiv_is_hidden(self):
        with tempfile.TemporaryDirectory(prefix='abyss-images-menu-test-') as tmp:
            root = Path(tmp)
            apps = root / 'data/applications'
            apps.mkdir(parents=True)
            shutil.copyfile(DESKTOP, apps / 'abyss-images.desktop')
            (apps / 'nsxiv.desktop').write_text('[Desktop Entry]\nType=Application\nName=nsxiv\nExec=nsxiv %F\nNoDisplay=true\n')
            env = os.environ.copy()
            env.update(XDG_DATA_HOME=str(root / 'data'), XDG_CACHE_HOME=str(root / 'cache'))
            output = subprocess.check_output([str(APPS), '--list'], env=env, text=True, timeout=15)
            self.assertIn('\texec:abyss-control-center images', output)
            self.assertNotIn('\texec:nsxiv', output)

if __name__ == '__main__':
    unittest.main()
