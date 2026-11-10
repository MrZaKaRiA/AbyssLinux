/* Exercises the dwm shortcut configuration parser without a running X server. */
#define _POSIX_C_SOURCE 200809L
#include <X11/Xlib.h>
#include <X11/Xatom.h>
#include <X11/keysym.h>
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#define LENGTH(a) (sizeof(a) / sizeof((a)[0]))
typedef union { int i; unsigned int ui; float f; const void *v; } Arg;
typedef struct { unsigned int mod; KeySym keysym; void (*func)(const Arg *); const Arg arg; } Key;
#define STUB(name) static void name(const Arg *arg) { (void)arg; }
STUB(spawn) STUB(togglescratch) STUB(togglebar) STUB(focusstack) STUB(movestack)
STUB(shiftview) STUB(shifttag) STUB(incnmaster) STUB(setmfact) STUB(zoom)
STUB(view) STUB(toggleview) STUB(tag) STUB(toggletag) STUB(killclient)
STUB(setlayout) STUB(togglefloating) STUB(focusmon) STUB(tagmon)
STUB(togglegaps) STUB(defaultgaps) STUB(incrgaps) STUB(quit)
static const char *termcmd[] = { "st", NULL }, *controlcentercmd[] = { "menu", NULL };
static const char *helpcmd[] = { "help", NULL }, *alacrittycmd[] = { "alt", NULL };
static const char *dmenucmd[] = { "dmenu", NULL }, *sshcmd[] = { "ssh", NULL };
static const char *browsercmd[] = { "browser", NULL }, *codecmd[] = { "code", NULL };
static const char *virtcmd[] = { "virt", NULL }, *lockcmd[] = { "lock", NULL };
static const char *screenscmd[] = { "screen", NULL }, *areascreenscmd[] = { "area", NULL };
static const Key keys[] = {
	{ Mod4Mask, XK_a, spawn, {.v = termcmd} },
	{ Mod4Mask, XK_b, spawn, {.v = browsercmd} },
	{ 0, XK_Print, spawn, {.v = screenscmd} },
};
static Display *dpy;
static Window root;
static void *ecalloc(size_t n, size_t size) { void *p = calloc(n, size); assert(p); return p; }
#include "../dwm/abyss-shortcuts.h"

static void
write_config(const char *path, const char *text)
{
	FILE *file = fopen(path, "w");
	assert(file);
	assert(fputs(text, file) >= 0);
	assert(fclose(file) == 0);
}

int
main(void)
{
	char temp[] = "/tmp/abyss-config-test.XXXXXX", dir[512], path[512];
	assert(mkdtemp(temp));
	assert(setenv("XDG_CONFIG_HOME", temp, 1) == 0);
	snprintf(dir, sizeof(dir), "%s/abyss", temp);
	assert(mkdir(dir, 0700) == 0);
	snprintf(path, sizeof(path), "%s/abyss/shortcuts.conf", temp);
	abyss_load_shortcuts();
	assert(abyss_keysyms[0] == XK_a && abyss_keymods[0] == Mod4Mask && abyss_appkey_count == 0);
	write_config(path, "B\t64\ta\t12\tc\nA\tapp-1\t64\td\tDemo\texec:demo\n");
	abyss_load_shortcuts();
	assert(abyss_keysyms[0] == XK_c && abyss_keymods[0] == 12);
	assert(abyss_appkey_count == 1 && abyss_appkeys[0].sym == XK_d && !strcmp(abyss_appkeys[0].action, "exec:demo"));
	write_config(path, "B\t64\ta\t64\tb\nB\t64\tb\t64\ta\n");
	abyss_load_shortcuts();
	assert(abyss_keysyms[0] == XK_b && abyss_keysyms[1] == XK_a);
	write_config(path, "A\tapp-1\t64\tb\tDemo\texec:demo\n");
	abyss_load_shortcuts();
	assert(abyss_keysyms[0] == XK_a && abyss_appkey_count == 0);
	write_config(path, "B\t64\ta\t0\t-\n");
	abyss_load_shortcuts();
	assert(abyss_keysyms[0] == NoSymbol && abyss_keysyms[1] == XK_b);
	write_config(path, "A\tbroken\t0\tnot-a-keysym\tDemo\texec:demo\n");
	abyss_load_shortcuts();
	assert(abyss_keysyms[0] == XK_a && abyss_appkey_count == 0);
	write_config(path, "A\tapp-1\t64\tc\tOne\texec:one\nA\tapp-1\t64\td\tTwo\texec:two\n");
	abyss_load_shortcuts();
	assert(abyss_keysyms[0] == XK_a && abyss_appkey_count == 0);
	puts("shortcut configuration parser: PASS");
	return 0;
}
