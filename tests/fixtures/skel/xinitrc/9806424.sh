#!/bin/sh
# ~/.xinitrc - Void Linux Suckless Developer Workstation

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

# X resources (xmenu theme for the Abyss menu)
[ -f "$HOME/.Xresources" ] && command -v xrdb >/dev/null 2>&1 && xrdb -merge "$HOME/.Xresources"

# HiDPI: Xft.dpi scales every point-sized font (dwm bar, st, dmenu, xmenu).
# 2x inside Apple Virtualization (Lumen and friends size the guest in Retina
# pixels) and from 1700 px screen height, 1.5x from 1300.
# Pin a value with: echo 144 > ~/.config/abyss/dpi
abyss_dpi=$(tr -dc 0-9 < "$HOME/.config/abyss/dpi" 2>/dev/null)
abyss_apple_vm=
grep -qs '^Apple' /sys/class/dmi/id/sys_vendor && abyss_apple_vm=1
grep -qsx '0x106b' /sys/bus/pci/devices/*/subsystem_vendor && abyss_apple_vm=1
if [ -z "$abyss_dpi" ]; then
    abyss_h=$(xrandr --current 2>/dev/null | sed -n 's/.* current [0-9]* x \([0-9]*\).*/\1/p' | head -n1)
    if [ -n "$abyss_apple_vm" ] || [ "${abyss_h:-0}" -ge 1700 ]; then abyss_dpi=192
    elif [ "${abyss_h:-0}" -ge 1300 ]; then abyss_dpi=144
    else abyss_dpi=96; fi
fi
if command -v xrdb >/dev/null 2>&1; then
    xrdb -merge <<EOF
Xft.dpi: $abyss_dpi
xmenu.width: $(( 230 * abyss_dpi / 96 ))
xmenu.height: $(( 28 * abyss_dpi / 96 ))
EOF
fi
unset abyss_dpi abyss_h abyss_apple_vm

# Keyboard: us,ara layouts, Alt+Shift toggle, Caps=Escape, Super fix inside VMs
/usr/local/bin/abyss-keyboard

# Desktop, Documents, Downloads, Music, Pictures, Videos... (their own folder
# icons in Thunar and the sidebar)
command -v xdg-user-dirs-update >/dev/null 2>&1 && xdg-user-dirs-update

# Start notification daemon, PipeWire audio, global hotkeys, and statusbar.
# The NetworkManager tray icon is opt-in: Abyss menu > System settings.
if command -v pipewire >/dev/null 2>&1 && ! pgrep -x pipewire >/dev/null 2>&1; then
    pipewire &
fi
command -v dunst >/dev/null 2>&1 && dunst &
if command -v sxhkd >/dev/null 2>&1 && [ -f "$HOME/.config/sxhkd/sxhkdrc" ]; then
    pgrep -u "$(id -u)" -x sxhkd >/dev/null 2>&1 || sxhkd &
fi
/usr/local/bin/dwm-statusbar &

# Set Abyss cosmic background
if command -v feh >/dev/null 2>&1 && [ -f /usr/share/backgrounds/abyss/abyss-wallpaper.jpg ]; then
    feh --bg-fill /usr/share/backgrounds/abyss/abyss-wallpaper.jpg &
else
    xsetroot -solid "#0b0914" &
fi

# Welcome hint instead of a full-screen terminal, so the desktop/wallpaper
# is what you see first. Super+F1 (or menu > Tools) opens the cheatsheet.
if command -v notify-send >/dev/null 2>&1; then
    (sleep 3 && notify-send -a "Abyss" -t 10000 "Welcome to Abyss Linux" \
        "Click Menu (top-right) - Super+F1 for shortcuts") &
fi

# Launch dwm (under dbus/elogind session if available)
if command -v dbus-run-session >/dev/null 2>&1 && [ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ]; then
    exec dbus-run-session dwm
else
    exec dwm
fi
