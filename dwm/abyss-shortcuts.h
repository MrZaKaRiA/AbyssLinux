/* Per-user dwm shortcut overrides and application shortcuts. */
#define ABYSS_MAX_APP_KEYS 64
#define ABYSS_SHORTCUTS_BUFFER (128 * 1024)

typedef struct {
	unsigned int mod;
	KeySym sym;
	char id[64];
	char label[256];
	char action[1024];
} AbyssAppKey;

static unsigned int abyss_keymods[LENGTH(keys)];
static KeySym abyss_keysyms[LENGTH(keys)];
static AbyssAppKey abyss_appkeys[ABYSS_MAX_APP_KEYS];
static size_t abyss_appkey_count;
static Atom abyss_shortcuts_atom, abyss_reload_atom;

static const char *
abyss_key_label(size_t i)
{
	const Key *key = &keys[i];
	if (key->func == spawn) {
		if (key->arg.v == termcmd) return "Open terminal";
		if (key->arg.v == controlcentercmd) return "Open Abyss menu";
		if (key->arg.v == helpcmd) return "Show keyboard shortcuts";
		if (key->arg.v == alacrittycmd) return "Open alternate terminal";
		if (key->arg.v == dmenucmd) return "Run a command";
		if (key->arg.v == sshcmd) return "Open SSH menu";
		if (key->arg.v == browsercmd) return "Open browser";
		if (key->arg.v == codecmd) return "Open VS Code";
		if (key->arg.v == virtcmd) return "Open virtual machines";
		if (key->arg.v == lockcmd) return "Lock screen";
		if (key->arg.v == screenscmd) return "Screenshot whole screen";
		if (key->arg.v == areascreenscmd) return "Screenshot selected area";
		return "Launch program";
	}
	if (key->func == togglescratch) return "Toggle scratchpad";
	if (key->func == togglebar) return "Toggle status bar";
	if (key->func == focusstack) return key->arg.i > 0 ? "Focus next window" : "Focus previous window";
	if (key->func == movestack) return key->arg.i > 0 ? "Move window down" : "Move window up";
	if (key->func == shiftview) return key->arg.i > 0 ? "Next tag" : "Previous tag";
	if (key->func == shifttag) return key->arg.i > 0 ? "Move window to next tag" : "Move window to previous tag";
	if (key->func == incnmaster) return key->arg.i > 0 ? "Add master window" : "Remove master window";
	if (key->func == setmfact) return key->arg.f > 0 ? "Grow master area" : "Shrink master area";
	if (key->func == zoom) return "Make window master";
	if (key->func == view) return "View tag";
	if (key->func == toggleview) return "Toggle tag view";
	if (key->func == tag) return "Move window to tag";
	if (key->func == toggletag) return "Toggle window tag";
	if (key->func == killclient) return "Close window";
	if (key->func == setlayout) return "Change layout";
	if (key->func == togglefloating) return "Toggle floating window";
	if (key->func == focusmon) return key->arg.i > 0 ? "Focus next monitor" : "Focus previous monitor";
	if (key->func == tagmon) return key->arg.i > 0 ? "Move window to next monitor" : "Move window to previous monitor";
	if (key->func == togglegaps) return "Toggle gaps";
	if (key->func == defaultgaps) return "Reset gaps";
	if (key->func == incrgaps) return key->arg.i > 0 ? "Increase gaps" : "Decrease gaps";
	if (key->func == quit) return "Log out";
	return "Window manager action";
}

static void
abyss_publish_shortcuts(void)
{
	char *buffer = ecalloc(ABYSS_SHORTCUTS_BUFFER, 1);
	size_t used = 0, i;
	int written;
	const char *oldname, *newname;
	for (i = 0; i < LENGTH(keys); i++) {
		oldname = XKeysymToString(keys[i].keysym);
		newname = abyss_keysyms[i] == NoSymbol ? "-" : XKeysymToString(abyss_keysyms[i]);
		if (!oldname || !newname) continue;
		written = snprintf(buffer + used, ABYSS_SHORTCUTS_BUFFER - used,
		                   "B\t%u\t%s\t%u\t%s\t%s\n", keys[i].mod, oldname,
		                   abyss_keymods[i], newname, abyss_key_label(i));
		if (written < 0 || (size_t)written >= ABYSS_SHORTCUTS_BUFFER - used) break;
		used += (size_t)written;
	}
	for (i = 0; i < abyss_appkey_count; i++) {
		newname = XKeysymToString(abyss_appkeys[i].sym);
		if (!newname) continue;
		written = snprintf(buffer + used, ABYSS_SHORTCUTS_BUFFER - used,
		                   "A\t%s\t%u\t%s\t%s\t%s\n", abyss_appkeys[i].id,
		                   abyss_appkeys[i].mod, newname, abyss_appkeys[i].label,
		                   abyss_appkeys[i].action);
		if (written < 0 || (size_t)written >= ABYSS_SHORTCUTS_BUFFER - used) break;
		used += (size_t)written;
	}
	XChangeProperty(dpy, root, abyss_shortcuts_atom, XA_STRING, 8,
	                PropModeReplace, (const unsigned char *)buffer, (int)used);
	free(buffer);
}

static void
abyss_shortcuts_defaults(void)
{
	size_t i;
	for (i = 0; i < LENGTH(keys); i++) {
		abyss_keymods[i] = keys[i].mod;
		abyss_keysyms[i] = keys[i].keysym;
	}
	abyss_appkey_count = 0;
}

static int
abyss_parse_modifier(const char *text, unsigned int *out)
{
	char *end;
	unsigned long value;
	if (!text || !*text) return 0;
	errno = 0;
	value = strtoul(text, &end, 10);
	if (errno || *end || (value & ~(ShiftMask | ControlMask | Mod1Mask | Mod4Mask))) return 0;
	*out = (unsigned int)value;
	return 1;
}

static void
abyss_load_shortcuts(void)
{
	char path[4096], line[8192], *field[6], *save, *p;
	const char *base = getenv("XDG_CONFIG_HOME"), *home = getenv("HOME");
	FILE *file;
	unsigned int oldmod, newmod;
	KeySym oldsym, newsym;
	size_t i, j, n;
	int invalid = 0;
	abyss_shortcuts_defaults();
	if (base && *base) snprintf(path, sizeof(path), "%s/abyss/shortcuts.conf", base);
	else if (home && *home) snprintf(path, sizeof(path), "%s/.config/abyss/shortcuts.conf", home);
	else return;
	file = fopen(path, "r");
	if (!file) return;
	while (fgets(line, sizeof(line), file)) {
		if (!strchr(line, '\n') && !feof(file)) { invalid = 1; break; }
		line[strcspn(line, "\r\n")] = '\0';
		if (!line[0] || line[0] == '#') continue;
		n = 0;
		for (p = strtok_r(line, "\t", &save); p && n < LENGTH(field); p = strtok_r(NULL, "\t", &save)) field[n++] = p;
		if (p || n == 0 || (strcmp(field[0], "B") && strcmp(field[0], "A")) ||
		    (!strcmp(field[0], "B") && n != 5) || (!strcmp(field[0], "A") && n != 6)) { invalid = 1; break; }
		if (!strcmp(field[0], "B")) {
			if (!abyss_parse_modifier(field[1], &oldmod) || !abyss_parse_modifier(field[3], &newmod)) { invalid = 1; break; }
			oldsym = XStringToKeysym(field[2]);
			newsym = !strcmp(field[4], "-") ? NoSymbol : XStringToKeysym(field[4]);
			if (oldsym == NoSymbol || (newsym == NoSymbol && strcmp(field[4], "-"))) { invalid = 1; break; }
			for (i = 0; i < LENGTH(keys); i++)
				if (keys[i].mod == oldmod && keys[i].keysym == oldsym) { abyss_keymods[i] = newmod; abyss_keysyms[i] = newsym; break; }
		} else {
			if (abyss_appkey_count >= ABYSS_MAX_APP_KEYS || !abyss_parse_modifier(field[2], &newmod) ||
			    (newsym = XStringToKeysym(field[3])) == NoSymbol || strlen(field[1]) >= sizeof(abyss_appkeys[0].id) ||
			    strlen(field[4]) >= sizeof(abyss_appkeys[0].label) || strlen(field[5]) >= sizeof(abyss_appkeys[0].action) ||
			    (strncmp(field[5], "exec:", 5) && strncmp(field[5], "term-exec:", 10))) { invalid = 1; break; }
			i = abyss_appkey_count++;
			abyss_appkeys[i].mod = newmod; abyss_appkeys[i].sym = newsym;
			snprintf(abyss_appkeys[i].id, sizeof(abyss_appkeys[i].id), "%s", field[1]);
			snprintf(abyss_appkeys[i].label, sizeof(abyss_appkeys[i].label), "%s", field[4]);
			snprintf(abyss_appkeys[i].action, sizeof(abyss_appkeys[i].action), "%s", field[5]);
		}
	}
	fclose(file);
	for (i = 0; !invalid && i < LENGTH(keys); i++) {
		if (abyss_keysyms[i] == NoSymbol) continue;
		for (j = i + 1; j < LENGTH(keys); j++)
			if (abyss_keysyms[i] == abyss_keysyms[j] && abyss_keymods[i] == abyss_keymods[j]) invalid = 1;
		for (j = 0; j < abyss_appkey_count; j++)
			if (abyss_keysyms[i] == abyss_appkeys[j].sym && abyss_keymods[i] == abyss_appkeys[j].mod) invalid = 1;
	}
	for (i = 0; !invalid && i < abyss_appkey_count; i++)
		for (j = i + 1; j < abyss_appkey_count; j++)
			if (!strcmp(abyss_appkeys[i].id, abyss_appkeys[j].id) ||
			    (abyss_appkeys[i].sym == abyss_appkeys[j].sym && abyss_appkeys[i].mod == abyss_appkeys[j].mod)) invalid = 1;
	if (invalid) {
		fprintf(stderr, "dwm: invalid or conflicting Abyss shortcut configuration; using defaults\n");
		abyss_shortcuts_defaults();
	}
}
