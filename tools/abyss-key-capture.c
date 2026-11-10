/* X11 key capture and passive-grab conflict checking for Abyss shortcuts. */
#include <X11/Xlib.h>
#include <X11/XKBlib.h>
#include <X11/Xutil.h>
#include <X11/Xatom.h>
#include <X11/keysym.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int grab_error;

static int
on_error(Display *display, XErrorEvent *event)
{
	(void)display;
	if (event->error_code == BadAccess || event->error_code == BadValue)
		grab_error = event->error_code;
	return 0;
}

static unsigned int
numlock_mask(Display *display)
{
	XModifierKeymap *map = XGetModifierMapping(display);
	KeyCode numlock = XKeysymToKeycode(display, XK_Num_Lock);
	unsigned int mask = 0;
	int modifier, slot;
	if (!map)
		return 0;
	for (modifier = 0; modifier < 8; modifier++)
		for (slot = 0; slot < map->max_keypermod; slot++)
			if (numlock && map->modifiermap[modifier * map->max_keypermod + slot] == numlock)
				mask |= 1U << modifier;
	XFreeModifiermap(map);
	return mask;
}

static int
capture(Display *display)
{
	Window root = DefaultRootWindow(display);
	XEvent event;
	KeySym sym;
	const char *name;
	unsigned int mask;
	if (XGrabKeyboard(display, root, False, GrabModeAsync, GrabModeAsync,
	                  CurrentTime) != GrabSuccess) {
		fprintf(stderr, "Could not capture the keyboard. Close other dialogs and try again.\n");
		return 1;
	}
	for (;;) {
		XNextEvent(display, &event);
		if (event.type != KeyPress)
			continue;
		sym = XkbKeycodeToKeysym(display, event.xkey.keycode, 0, 0);
		if (sym == NoSymbol || IsModifierKey(sym))
			continue;
		mask = event.xkey.state & (ShiftMask | ControlMask | Mod1Mask | Mod4Mask);
		if (sym == XK_Escape && mask == 0) {
			XUngrabKeyboard(display, CurrentTime);
			return 2;
		}
		name = XKeysymToString(sym);
		if (!name)
			continue;
		printf("%u\t%s\n", mask, name);
		XUngrabKeyboard(display, CurrentTime);
		return 0;
	}
}

static int
probe(Display *display, const char *mask_arg, const char *key_arg)
{
	Window root = DefaultRootWindow(display);
	char *end;
	unsigned long mask;
	unsigned int locks[4], numlock, i;
	KeySym sym;
	KeyCode code;
	int (*previous_handler)(Display *, XErrorEvent *);
	errno = 0;
	mask = strtoul(mask_arg, &end, 10);
	if (errno || !*mask_arg || *end || (mask & ~(ShiftMask | ControlMask | Mod1Mask | Mod4Mask)))
		return 2;
	sym = XStringToKeysym(key_arg);
	code = sym == NoSymbol ? 0 : XKeysymToKeycode(display, sym);
	if (!code)
		return 2;
	numlock = numlock_mask(display);
	locks[0] = 0; locks[1] = LockMask; locks[2] = numlock; locks[3] = LockMask | numlock;
	grab_error = 0;
	previous_handler = XSetErrorHandler(on_error);
	for (i = 0; i < 4; i++)
		XGrabKey(display, code, (unsigned int)mask | locks[i], root, False,
		         GrabModeAsync, GrabModeAsync);
	XSync(display, False);
	for (i = 0; i < 4; i++)
		XUngrabKey(display, code, (unsigned int)mask | locks[i], root);
	XSync(display, False);
	XSetErrorHandler(previous_handler);
	return grab_error ? 3 : 0;
}

/* dwm publishes its current bindings as UTF-8 records on the root window. */
static int
list_bindings(Display *display)
{
	Atom property = XInternAtom(display, "_ABYSS_SHORTCUTS", False), type;
	int format;
	unsigned long count, remaining;
	unsigned char *value = NULL;
	int status = XGetWindowProperty(display, DefaultRootWindow(display), property,
	                                0, 1024 * 1024, False, AnyPropertyType,
	                                &type, &format, &count, &remaining, &value);
	if (status != Success || type == None || format != 8 || remaining != 0) {
		if (value) XFree(value);
		fprintf(stderr, "The running window manager has not published shortcut settings.\n");
		return 1;
	}
	if (count && fwrite(value, 1, count, stdout) != count) {
		XFree(value);
		return 1;
	}
	if (value) XFree(value);
	return 0;
}

static int
reload_bindings(Display *display)
{
	Atom property = XInternAtom(display, "_ABYSS_SHORTCUTS_RELOAD", False);
	unsigned long value = 1;
	XChangeProperty(display, DefaultRootWindow(display), property, XA_INTEGER,
	                32, PropModeReplace, (const unsigned char *)&value, 1);
	XSync(display, False);
	return 0;
}

int
main(int argc, char **argv)
{
	Display *display;
	int result;
	if (!((argc == 2 && (!strcmp(argv[1], "--capture") ||
	                    !strcmp(argv[1], "--list") || !strcmp(argv[1], "--reload"))) ||
	      (argc == 4 && !strcmp(argv[1], "--probe")))) {
		fprintf(stderr, "usage: abyss-key-capture --capture | --list | --reload | --probe MASK KEYSYM\n");
		return 2;
	}
	display = XOpenDisplay(NULL);
	if (!display) {
		fprintf(stderr, "Cannot connect to the X display.\n");
		return 1;
	}
	if (argc == 4) result = probe(display, argv[2], argv[3]);
	else if (!strcmp(argv[1], "--capture")) result = capture(display);
	else if (!strcmp(argv[1], "--list")) result = list_bindings(display);
	else result = reload_bindings(display);
	XCloseDisplay(display);
	return result;
}
