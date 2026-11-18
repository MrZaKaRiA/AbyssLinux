"""The status bar's Passwords menu (abyss-bar, block 3): logins saved the way
Browserpass finds them (<domain>/<username>, password first, then login: and
url:), the "domain — username" listing, verification codes (pass-otp), and
browser autofill (the Browserpass native host for Firefox, Chromium, Chrome).

pass, dmenu, xclip and the browsers are stubs: the fake pass keeps entries as
plain text, so the tests read what abyss-bar saved. The dmenu stub answers by
prompt from $HOME/answers ("prompt part<TAB>answer", each line used once; no
line is Esc)."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_statusbar import BAR, Sandbox, stub, write  # noqa: E402

FAKE_PASS = r'''
echo "pass $*" >> "$HOME/calls.log"
S=${PASSWORD_STORE_DIR:-$HOME/.password-store}
cmd=$1; shift
case $cmd in
    otp) case $1 in version) [ -e "$HOME/otp" ] ;; code) echo 123456 > "$HOME/clipboard" ;; esac; exit ;;
esac
clip=
while [ $# -gt 0 ]; do
    case $1 in -c) clip=1 ;; --) shift; break ;; -*) ;; *) break ;; esac
    shift
done
case $cmd in
    insert) mkdir -p "$(dirname "$S/$1")" && cat > "$S/$1.gpg" ;;
    show)   [ -f "$S/$1.gpg" ] || exit 1
            if [ -n "$clip" ]; then head -n 1 "$S/$1.gpg" > "$HOME/clipboard"; else cat "$S/$1.gpg"; fi ;;
    rm)     rm "$S/$1.gpg" ;;
esac
'''

# Answers by prompt; logs each prompt (and -P) to prompts.log.
FAKE_DMENU = r'''
prompt= hidden=
while [ $# -gt 0 ]; do
    case $1 in -p) prompt=$2; shift ;; -P) hidden=' (hidden)' ;; esac
    shift
done
printf '%s%s\n' "$prompt" "$hidden" >> "$HOME/prompts.log"
cat > "$HOME/dmenu.last"
cat "$HOME/dmenu.last" >> "$HOME/dmenu.in"
[ -f "$HOME/answers" ] || exit 1
awk -F'\t' -v p="$prompt" -v out="$HOME/answer" '
    !done && index(p, $1) { print $2 > out; done = 1; next } { print }' "$HOME/answers" > "$HOME/answers.new"
mv "$HOME/answers.new" "$HOME/answers"
[ -f "$HOME/answer" ] || exit 1
cat "$HOME/answer"; rm -f "$HOME/answer"
'''

# Like xclip, stays in the background (here with the same stdout) to serve
# the clipboard: a caller that waits for its output hangs.
FAKE_XCLIP = r'''
case "$*" in *-o*) cat "$HOME/clipboard" 2>/dev/null; exit ;; esac
cat > "$HOME/clipboard"
sleep 60 &
'''

# Only these system tools: CI runners have browsers in /usr/bin, the tests
# decide which browsers there are.
TOOLS = ('sh dash bash awk sed grep find sort cut tr head tail cat mkdir rm mv dirname basename '
         'sleep id env wc ls').split()

PASSWORD = re.compile(r'^[A-Za-z0-9]{6}-[A-Za-z0-9]{6}-[A-Za-z0-9]{6}$')


class PasswordsTest(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox()
        self.addCleanup(self.box.close)
        self.home = self.box.home
        self.store = self.home / '.password-store'
        stub(self.box.bin, 'pass', FAKE_PASS)
        stub(self.box.bin, 'dmenu', FAKE_DMENU)
        stub(self.box.bin, 'xclip', FAKE_XCLIP)
        write(self.store / '.gpg-id', 'ABC\n')
        self.root = self.home / 'root'           # system folders for the native host
        self.root.mkdir()
        self.tools = self.home / 'tools'
        self.tools.mkdir()
        for tool in TOOLS:
            found = shutil.which(tool)
            if found:
                (self.tools / tool).symlink_to(found)

    # helpers ----------------------------------------------------------------
    def bar(self, *args, status=0, **env):
        env = self.box.env(ABYSS_BROWSERPASS_ROOT=str(self.root), PASSWORD_STORE_CLIP_TIME='1',
                           PATH=f'{self.box.bin}:{self.tools}', **env)
        result = subprocess.run(['/bin/sh', str(BAR), *args], env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, timeout=30)
        self.assertEqual(result.returncode, status, result.stderr)
        return result.stdout

    def act(self, action, *answers):
        """Click the key icon, pick ACTION, answer the dmenu prompts."""
        self.box.file('pick', action + '\n')
        self.box.file('answers', ''.join(f'{p}\t{a}\n' for p, a in answers))
        for name in ('prompts.log', 'dmenu.in', 'calls.log'):
            (self.home / name).unlink(missing_ok=True)
        self.bar('--click', '3', '1')

    def menu(self):
        return (self.home / 'menu.in').read_text()

    def prompts(self):
        path = self.home / 'prompts.log'
        return path.read_text().splitlines() if path.exists() else []

    def listed(self):
        path = self.home / 'dmenu.in'
        return path.read_text() if path.exists() else ''

    def entry(self, name):
        return (self.store / f'{name}.gpg').read_text()

    def save(self, name, text):
        write(self.store / f'{name}.gpg', text)

    def clipboard(self):
        path = self.home / 'clipboard'
        return path.read_text() if path.exists() else ''

    # adding logins ------------------------------------------------------------
    def test_add_login_with_a_generated_password(self):
        self.act('pass-add', ('Website', 'https://www.GitHub.com/login?next=1'),
                 ('Username or email', 'me@example.com'),
                 ('Password for', '󰒃  Generate strong password'),
                 ('Strong password', '󰆏  Use it and copy it'),
                 ('Notes', 'work account'))
        lines = self.entry('github.com/me@example.com').splitlines()
        self.assertRegex(lines[0], PASSWORD)
        self.assertEqual(lines[1:], ['login: me@example.com', 'url: https://github.com/', 'notes: work account'])
        self.assertEqual(self.clipboard(), lines[0])
        prompts = self.prompts()
        self.assertEqual(prompts[0], 'Website (github.com or a full address)')
        self.assertEqual(prompts[1], 'Username or email for github.com')
        self.assertEqual(prompts[2], 'Password for github.com — me@example.com')
        self.assertEqual(prompts[3], f'Strong password: {lines[0]}')   # shown, so it can be copied
        self.assertIn('pass insert -m -f -- github.com/me@example.com', self.box.calls())

    def test_generate_is_the_default_and_another_can_be_asked_for(self):
        self.act('pass-add', ('Website', 'example.com'), ('Username', 'bob'),
                 ('Password for', '󰒃  Generate strong password'),
                 ('Strong password', '󰑐  Generate another'), ('Strong password', '󰄬  Use this password'))
        self.assertTrue(self.listed().startswith('󰒃  Generate strong password\n󰌌  Type a password\n'))
        shown = [p.split(': ', 1)[1] for p in self.prompts() if p.startswith('Strong password')]
        self.assertEqual(len(shown), 2)
        self.assertEqual(self.entry('example.com/bob').splitlines()[0], shown[1])
        self.assertEqual(self.clipboard(), '')

    def test_add_login_with_a_typed_hidden_password(self):
        self.act('pass-add', ('Website', 'example.org'), ('Username', 'alice'),
                 ('Password for', '󰌌  Type a password'), ('Password for', 'pa$$ word'))
        self.assertEqual(self.entry('example.org/alice'),
                         'pa$$ word\nlogin: alice\nurl: https://example.org/\n')
        self.assertIn('Password for example.org — alice (hidden)', self.prompts())

    def test_website_is_normalised_to_its_domain(self):
        cases = {
            'github.com': ('github.com', 'https://github.com/'),
            'HTTP://Login.Example.co.uk:8080/a/b#c': ('login.example.co.uk:8080', 'http://login.example.co.uk:8080/'),
            'https://user@www.example.com:443/': ('example.com', 'https://example.com/'),
            'localhost:3000': ('localhost:3000', 'https://localhost:3000/'),
            '10.0.2.2:8000/login.html': ('10.0.2.2:8000', 'https://10.0.2.2:8000/'),
            '  shop.example.net.  ': ('shop.example.net', 'https://shop.example.net/'),
        }
        for typed, (domain, url) in cases.items():
            with self.subTest(typed):
                self.act('pass-add', ('Website', typed), ('Username', 'u'),
                         ('Password for', 'Type'), ('Password for', 'pw'))
                self.assertEqual(self.entry(f'{domain}/u'), f'pw\nlogin: u\nurl: {url}\n')

    def test_not_a_website_saves_nothing(self):
        for typed in ('github', 'exa mple.com', 'https://', 'a..b.com'):
            with self.subTest(typed):
                self.act('pass-add', ('Website', typed), ('Username', 'u'),
                         ('Password for', 'Type'), ('Password for', 'pw'))
                self.assertEqual(len(self.prompts()), 1)
                self.assertIn('Not a website address', self.box.calls())
        self.assertEqual(sorted(p.name for p in self.store.rglob('*.gpg')), [])

    def test_bad_usernames_and_no_username(self):
        for user in ('a/b', "o'neil", '-x', '../x'):
            with self.subTest(user):
                self.act('pass-add', ('Website', 'example.com'), ('Username', user),
                         ('Password for', 'Type'), ('Password for', 'pw'))
                self.assertEqual(list(self.store.rglob('*.gpg')), [])
        self.act('pass-add', ('Website', 'example.com'), ('Username', ''),
                 ('Password for', 'Type'), ('Password for', 'pw'))
        self.assertEqual(self.entry('example.com'), 'pw\nurl: https://example.com/\n')

    def test_an_existing_login_is_replaced_only_when_asked(self):
        self.save('example.com/bob', 'old\nlogin: bob\n')
        self.act('pass-add', ('Website', 'example.com'), ('Username', 'bob'), ('already saved', 'Cancel'))
        self.assertEqual(self.entry('example.com/bob'), 'old\nlogin: bob\n')
        self.act('pass-add', ('Website', 'example.com'), ('Username', 'bob'), ('already saved', 'Replace it'),
                 ('Password for', 'Type'), ('Password for', 'new'))
        self.assertEqual(self.entry('example.com/bob').splitlines()[0], 'new')

    def test_verification_code_setup_key(self):
        self.box.file('otp', '')
        self.act('pass-add', ('Website', 'example.com'), ('Username', 'bob smith'),
                 ('Password for', 'Type'), ('Password for', 'pw'),
                 ('Verification code', 'jbsw y3dp ehpk 3pxp'))
        self.assertIn('otpauth://totp/example.com:bob%20smith?secret=JBSWY3DPEHPK3PXP&issuer=example.com\n',
                      self.entry('example.com/bob smith'))
        link = 'otpauth://totp/GitHub:me?secret=ABC&issuer=GitHub'
        self.act('pass-add', ('Website', 'github.com'), ('Username', 'me'),
                 ('Password for', 'Type'), ('Password for', 'pw'), ('Verification code', link))
        self.assertIn(link + '\n', self.entry('github.com/me'))
        self.act('pass-add', ('Website', 'gitlab.com'), ('Username', 'me'),
                 ('Password for', 'Type'), ('Password for', 'pw'), ('Verification code', 'not base32!'))
        self.assertNotIn('otpauth', self.entry('gitlab.com/me'))

    def test_no_verification_code_prompt_without_pass_otp(self):
        self.act('pass-add', ('Website', 'example.com'), ('Username', 'bob'),
                 ('Password for', 'Type'), ('Password for', 'pw'))
        self.assertFalse(any('Verification' in p for p in self.prompts()))

    # the menu and the listing ---------------------------------------------------
    def fill_store(self):
        self.save('github.com/me@example.com', 'pw1\nlogin: me@example.com\nurl: https://github.com/\n')
        self.save('web/github', 'legacy\nuser = nobody\n')
        self.save('work/gitlab.com/bob', 'pw3\nlogin: bob\n')
        self.save('example.org', 'pw4\nusername: carol\n')
        self.save('otp.example.com/dave', 'pw5\nlogin: dave\notpauth://totp/x:dave?secret=ABC\n')

    def test_menu_puts_add_search_and_autofill_first(self):
        self.fill_store()
        self.act('')
        rows = [r for r in self.menu().splitlines() if r]
        self.assertEqual(rows[0], '󰌋  Passwords · 5 saved\t-')
        self.assertEqual(rows[1], '󰐕  Add login…\tpass-add')
        self.assertEqual(rows[2], '󰍉  Search logins…\tpass-search')
        self.assertTrue(rows[3].startswith('󰖟  Set up browser autofill…  (not installed)\tpass-autofill'), rows[3])
        for action in ('pass-copy', 'pass-user', 'pass-edit', 'pass-delete', 'pass-generate'):
            self.assertIn(f'\t{action}', self.menu())
        self.assertNotIn('pass-otp', self.menu())
        self.box.file('otp', '')
        self.act('')
        self.assertIn('Copy one-time code…\tpass-otp', self.menu())

    def test_listing_shows_domain_and_username(self):
        self.fill_store()
        self.act('pass-search')
        self.assertEqual(self.listed().splitlines(), [
            'example.org', 'github.com — me@example.com', 'gitlab.com — bob  · work',
            'otp.example.com — dave', 'web/github'])

    def test_copy_password_and_username(self):
        self.fill_store()
        self.act('pass-copy', ('Copy password', 'github.com — me@example.com'))
        self.assertIn('pass show -c -- github.com/me@example.com', self.box.calls())
        self.assertEqual(self.clipboard(), 'pw1\n')
        for label, user in (('github.com — me@example.com', 'me@example.com'),
                            ('example.org', 'carol'), ('gitlab.com — bob  · work', 'bob')):
            with self.subTest(label):
                self.act('pass-user', ('Copy username', label))
                self.assertEqual(self.clipboard(), user)

    def test_old_entries_keep_working(self):
        self.fill_store()
        self.act('pass-copy', ('Copy password', 'web/github'))
        self.assertEqual(self.clipboard(), 'legacy\n')
        self.act('pass-search', ('Search logins', 'web/github'), ('web/github', '󰆏  Copy password'))
        self.assertNotIn('Copy username', self.listed())
        self.assertEqual(self.clipboard(), 'legacy\n')

    def test_search_shows_a_login_with_its_one_time_code(self):
        self.fill_store()
        self.box.file('otp', '')
        self.act('pass-search', ('Search logins', 'otp.example.com — dave'),
                 ('otp.example.com — dave', '󰦯  Copy one-time code'))
        self.assertIn('󰀄  Copy username: dave\n󰦯  Copy one-time code\n', self.listed())
        self.assertIn('pass otp code -c -- otp.example.com/dave', self.box.calls())
        self.assertEqual(self.clipboard(), '123456\n')
        self.act('pass-search', ('Search logins', 'github.com — me@example.com'))
        self.assertNotIn('one-time code', self.listed())
        self.assertIn('󰖟  Open https://github.com/', self.listed())

    def test_change_password_keeps_the_other_fields(self):
        self.fill_store()
        self.act('pass-edit', ('Edit login', 'github.com — me@example.com'),
                 ('github.com — me@example.com', '󰏫  Change password…'),
                 ('Password for', 'Type'), ('Password for', 'newpw'))
        self.assertEqual(self.entry('github.com/me@example.com'),
                         'newpw\nlogin: me@example.com\nurl: https://github.com/\n')

    def test_change_username_renames_the_login(self):
        self.fill_store()
        self.act('pass-edit', ('Edit login', 'github.com — me@example.com'),
                 ('github.com — me@example.com', '󰀄  Change username…'), ('New username', 'new@example.com'))
        self.assertFalse((self.store / 'github.com/me@example.com.gpg').exists())
        self.assertEqual(self.entry('github.com/new@example.com'),
                         'pw1\nlogin: new@example.com\nurl: https://github.com/\n')
        self.act('pass-edit', ('Edit login', 'example.org'), ('example.org', '󰀄  Change username…'),
                 ('New username', 'carol2'))
        self.assertEqual(self.entry('example.org/carol2'), 'pw4\nlogin: carol2\n')
        self.assertFalse((self.store / 'example.org.gpg').exists())

    def test_delete_asks_first(self):
        self.fill_store()
        self.act('pass-delete', ('Delete login', 'example.org'), ('Delete example.org?', 'Keep it'))
        self.assertTrue((self.store / 'example.org.gpg').exists())
        self.assertTrue(self.listed().endswith('Keep it\nDelete example.org\n'))   # keeping is the default
        self.act('pass-delete', ('Delete login', 'example.org'), ('Delete example.org?', 'Delete example.org'))
        self.assertFalse((self.store / 'example.org.gpg').exists())

    def test_copy_a_new_strong_password(self):
        self.act('pass-generate')
        self.assertRegex(self.clipboard(), PASSWORD)
        self.assertEqual(list(self.store.rglob('*.gpg')), [])

    # browser autofill -------------------------------------------------------------
    def browsers(self, *names):
        for name in names:
            stub(self.box.bin, name, 'echo "%s $*" >> "$HOME/calls.log"' % name)
        stub(self.box.bin, 'browserpass-native', 'exit 0')

    def test_system_hosts_from_the_void_package(self):
        self.browsers('firefox', 'chromium')
        host = 'com.github.browserpass.native.json'
        write(self.root / 'usr/lib/mozilla/native-messaging-hosts' / host, '{}')
        write(self.root / 'etc/chromium/native-messaging-hosts' / host, '{}')
        write(self.root / 'etc/chromium/policies/managed' / host, '{}')
        out = self.bar('--autofill-setup')
        self.assertIn(f'Firefox: native host {self.root}/usr/lib/mozilla/native-messaging-hosts/{host}', out)
        self.assertIn(f'Chromium: native host {self.root}/etc/chromium/native-messaging-hosts/{host}', out)
        self.assertIn('Chromium installs the Browserpass extension by itself', out)
        calls = self.box.calls()
        self.assertIn('firefox https://addons.mozilla.org/firefox/addon/browserpass-ce/', calls)
        self.assertNotIn('chromium https', calls)
        self.assertFalse((self.home / '.mozilla/native-messaging-hosts').exists())
        self.assertFalse((self.home / 'config/mozilla/native-messaging-hosts').exists())
        self.assertFalse((self.home / 'config/chromium/NativeMessagingHosts').exists())

    def test_user_hosts_where_there_is_no_system_host(self):
        self.browsers('firefox', 'chromium', 'google-chrome-stable')
        out = self.bar('--autofill-setup')
        native = str(self.box.bin / 'browserpass-native')
        host = 'com.github.browserpass.native.json'
        for folder in ('.mozilla', 'config/mozilla'):      # Firefox before and after 147 (XDG)
            ff = json.loads((self.home / folder / 'native-messaging-hosts' / host).read_text())
            self.assertEqual((ff['name'], ff['path'], ff['type'], ff['allowed_extensions']),
                             ('com.github.browserpass.native', native, 'stdio', ['browserpass@maximbaz.com']))
        for folder in ('chromium', 'google-chrome'):
            cr = json.loads((self.home / 'config' / folder / 'NativeMessagingHosts' / host).read_text())
            self.assertEqual(cr['path'], native)
            self.assertIn('chrome-extension://naepdomgkenhinolocfifgehidddafch/', cr['allowed_origins'])
        calls = self.box.calls()
        store_page = 'https://chromewebstore.google.com/detail/browserpass/naepdomgkenhinolocfifgehidddafch'
        self.assertIn(f'chromium {store_page}', calls)
        self.assertIn(f'google-chrome-stable {store_page}', calls)
        self.assertIn('Google Chrome: native host', out)

    def test_installed_extensions_are_not_opened_again(self):
        self.browsers('firefox')
        write(self.root / 'usr/lib/mozilla/native-messaging-hosts/com.github.browserpass.native.json', '{}')
        write(self.home / '.mozilla/firefox/abc.default-release/extensions/browserpass@maximbaz.com.xpi', '')
        out = self.bar('--autofill-setup')
        self.assertIn('Browserpass extension installed', out)
        self.assertNotIn('firefox http', self.box.calls())

    def test_autofill_status_in_the_menu(self):
        self.act('')
        self.assertIn('Set up browser autofill…  (not installed)\tpass-autofill', self.menu())
        self.browsers()
        self.act('')
        self.assertIn('Set up browser autofill…  (no browser installed)', self.menu())
        self.browsers('firefox', 'chromium')
        write(self.root / 'usr/lib/mozilla/native-messaging-hosts/com.github.browserpass.native.json', '{}')
        write(self.home / 'config/mozilla/firefox/p.default/extensions/browserpass@maximbaz.com.xpi', '')
        self.act('')
        self.assertIn('Set up browser autofill…  (Firefox ✓, Chromium: not set up)', self.menu())
        write(self.root / 'etc/chromium/native-messaging-hosts/com.github.browserpass.native.json', '{}')
        self.act('')
        self.assertIn('(Firefox ✓, Chromium: add the extension)', self.menu())
        write(self.root / 'etc/chromium/policies/managed/com.github.browserpass.native.json', '{}')
        self.act('')
        self.assertIn('(Firefox ✓, Chromium: start it once)', self.menu())   # the policy installs it
        (self.home / 'config/chromium/Default/Extensions/naepdomgkenhinolocfifgehidddafch').mkdir(parents=True)
        self.act('pass-autofill')
        self.assertIn('(Firefox ✓, Chromium ✓)', self.menu())
        self.assertIn('st -t Browser autofill', self.box.calls())

    def test_autofill_without_browserpass_installs_the_bundle(self):
        self.act('pass-autofill')
        self.assertIn('abyss-software --install pass pass-otp browserpass pinentry-gtk xclip', self.box.calls())

    def test_setup_without_browserpass_explains(self):
        out = self.bar('--autofill-setup', status=1)
        self.assertIn('browserpass is not installed', out)


if __name__ == '__main__':
    unittest.main()
