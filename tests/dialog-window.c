/* Exercise oversized transient windows and subsequent configure requests. */
#include <X11/Xlib.h>
#include <X11/Xatom.h>
#include <stdio.h>
#include <unistd.h>

static int fits(Display *dpy, Window w, const char *stage) {
    Window root, child;
    int x, y, rx, ry;
    unsigned int width, height, border, depth;
    if (!XGetGeometry(dpy, w, &root, &x, &y, &width, &height, &border, &depth)) return 0;
    XTranslateCoordinates(dpy, w, root, 0, 0, &rx, &ry, &child);
    if (width > 1280 || height > 900 || rx < 0 || ry < 0 || rx + (int)width > 1280 || ry + (int)height > 900) {
        fprintf(stderr, "%s: dialog outside screen: %ux%u at %d,%d\n", stage, width, height, rx, ry);
        return 0;
    }
    return 1;
}
int main(void) {
    Display *dpy = XOpenDisplay(NULL);
    if (!dpy) return 1;
    Window root = DefaultRootWindow(dpy);
    Window parent = XCreateSimpleWindow(dpy, root, 0, 0, 600, 400, 0, 0, 0);
    XStoreName(dpy, parent, "dialog test parent");
    XMapWindow(dpy, parent);
    XFlush(dpy);
    sleep(1);
    Window dialog = XCreateSimpleWindow(dpy, root, 0, 0, 2400, 1800, 0, 0, 0);
    Atom type = XInternAtom(dpy, "_NET_WM_WINDOW_TYPE", False);
    Atom dtype = XInternAtom(dpy, "_NET_WM_WINDOW_TYPE_DIALOG", False);
    XSetTransientForHint(dpy, dialog, parent);
    XChangeProperty(dpy, dialog, type, XA_ATOM, 32, PropModeReplace, (unsigned char *)&dtype, 1);
    XMapWindow(dpy, dialog);
    XFlush(dpy);
    sleep(1);
    if (!fits(dpy, dialog, "initial")) return 1;
    XResizeWindow(dpy, dialog, 2800, 2000);
    XFlush(dpy);
    sleep(1);
    if (!fits(dpy, dialog, "resize request")) return 1;
    XDestroyWindow(dpy, dialog);
    XDestroyWindow(dpy, parent);
    XCloseDisplay(dpy);
    puts("Oversized floating dialogs stay on screen: PASS");
    return 0;
}
