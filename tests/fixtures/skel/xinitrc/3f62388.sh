#!/bin/sh
# ~/.xinitrc - Abyss Linux minimal suckless desktop

# Start the session bus before any user services, including PipeWire.
if command -v dbus-run-session >/dev/null 2>&1 && [ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ] && [ -z "${ABYSS_DBUS_STARTED:-}" ]; then
    export ABYSS_DBUS_STARTED=1
    exec dbus-run-session /bin/sh "$0" "$@"
fi

export PATH="/usr/local/bin:${HOME}/.local/bin:${PATH}"

if [ -z "${XDG_RUNTIME_DIR:-}" ] || [ ! -w "${XDG_RUNTIME_DIR}" ]; then
    export XDG_RUNTIME_DIR="/tmp/runtime-$(id -u)"
    mkdir -p -m 0700 "${XDG_RUNTIME_DIR}" 2>/dev/null || true
fi

if [ -d /etc/X11/xinit/xinitrc.d ]; then
    for f in /etc/X11/xinit/xinitrc.d/?*.sh; do
        [ -x "$f" ] && . "$f"
    done
    unset f
fi

# Fix Java/GUI toolkit rendering in tiling WMs
command -v wmname >/dev/null 2>&1 && wmname LG3D &

# Match libadwaita applications to Abyss's dark desktop, including under startx.
# Set ADW_DEBUG_COLOR_SCHEME explicitly to choose another appearance.
: "${ADW_DEBUG_COLOR_SCHEME:=prefer-dark}"
export ADW_DEBUG_COLOR_SCHEME

# X resources (dmenu and Abyss theme)
[ -f "$HOME/.Xresources" ] && command -v xrdb >/dev/null 2>&1 && xrdb -merge "$HOME/.Xresources"

# Optional idle blanking for OLED screens, toggled from the display menu.
if [ "$(cat "$HOME/.config/abyss/oled-blanking" 2>/dev/null)" = 1 ]; then
    xset s 600 600; xset +dpms; xset dpms 600 600 600
else
    xset s off; xset -dpms
fi

# Restore a saved monitor mode/refresh profile, then enable any new outputs.
command -v abyss-display >/dev/null 2>&1 && abyss-display --restore >/dev/null 2>&1

# Display scale (Xft.dpi, xmenu size, pointer), sized for the screen the
# layout above turned on, by abyss-scale, which also follows later resolution
# changes. Choose another one in Menu > Settings > Display, or pin one with:
# echo 144 > ~/.config/abyss/dpi
command -v abyss-scale >/dev/null 2>&1 && abyss-scale --login

# Keyboard: us,ara layouts, Alt+Shift toggle, Caps=Escape, Super fix inside VMs
/usr/local/bin/abyss-keyboard

# Index installed desktop apps for the menu; the image ships with no apps.
[ -x /usr/local/bin/abyss-apps ] && /usr/local/bin/abyss-apps --refresh >/dev/null 2>&1 &

# Create standard user folders when the matching Void utility is installed.
command -v xdg-user-dirs-update >/dev/null 2>&1 && xdg-user-dirs-update

# Start optional PipeWire components if the user installed audio support.
if command -v pipewire >/dev/null 2>&1 && ! pgrep -u "$(id -u)" -x pipewire >/dev/null 2>&1; then
    pipewire &
fi
if command -v wireplumber >/dev/null 2>&1 && ! pgrep -u "$(id -u)" -x wireplumber >/dev/null 2>&1; then
    wireplumber &
fi
if command -v pipewire-pulse >/dev/null 2>&1 && ! pgrep -u "$(id -u)" -x pipewire-pulse >/dev/null 2>&1; then
    pipewire-pulse &
fi
# xss-lock listens for elogind sleep/lock requests, including lid close.
if [ -z "${ABYSS_LOCK_LISTENER_STARTED:-}" ] && command -v xss-lock >/dev/null 2>&1 && command -v slock >/dev/null 2>&1 && ! pgrep -u "$(id -u)" -x xss-lock >/dev/null 2>&1; then
    xss-lock --transfer-sleep-lock -- slock &
fi
/usr/local/bin/dwm-statusbar &

# Desktop background: the Abyss wallpaper, or the choice saved in
# ~/.config/abyss/wallpaper ("none" for plain black, or the path of an image).
if command -v abyss-wallpaper >/dev/null 2>&1; then abyss-wallpaper &
else xsetroot -solid "#000000" & fi

# Offer the optional setup window on first login (the user can defer it).
command -v abyss-setup >/dev/null 2>&1 && abyss-setup --first-run &

# Launch dwm (under dbus/elogind session if available)
if command -v dbus-run-session >/dev/null 2>&1 && [ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ]; then
    exec dbus-run-session dwm
else
    exec dwm
fi
