#!/bin/sh
# ~/.xinitrc - Abyss Linux minimal suckless desktop

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

# X resources (dmenu and Abyss theme)
[ -f "$HOME/.Xresources" ] && command -v xrdb >/dev/null 2>&1 && xrdb -merge "$HOME/.Xresources"

# HiDPI: Xft.dpi scales point-sized fonts across the X screen. The height
# heuristic uses the largest connected output, so an ultrawide or a second
# monitor does not accidentally scale the whole desktop by the combined size.
# Pin a value with: echo 144 > ~/.config/abyss/dpi
abyss_dpi=$(tr -dc 0-9 < "$HOME/.config/abyss/dpi" 2>/dev/null)
abyss_apple_vm=
grep -qs '^Apple' /sys/class/dmi/id/sys_vendor && abyss_apple_vm=1
grep -qsx '0x106b' /sys/bus/pci/devices/*/subsystem_vendor && abyss_apple_vm=1
if [ -z "$abyss_dpi" ]; then
    abyss_h=$(xrandr --query 2>/dev/null | awk '$2 == "connected" {for(i=3;i<=NF;i++) if ($i ~ /^[0-9]+x[0-9]+[+-]/) {v=$i; sub(/[+-].*/, "", v); split(v,a,"x"); if (a[2] > h) h=a[2]}} END {print h+0}')
    if [ -n "$abyss_apple_vm" ] || [ "${abyss_h:-0}" -ge 1700 ]; then abyss_dpi=192
    elif [ "${abyss_h:-0}" -ge 1300 ]; then abyss_dpi=144
    else abyss_dpi=96; fi
fi
if command -v xrdb >/dev/null 2>&1; then
    xrdb -merge <<EOF
Xft.dpi: $abyss_dpi
xmenu.width: $(( 260 * abyss_dpi / 96 ))
xmenu.height: $(( 28 * abyss_dpi / 96 ))
EOF
fi
unset abyss_dpi abyss_h abyss_apple_vm

# OLED-friendly black desktop background; enable optional idle blanking from
# the display menu. This avoids requiring a wallpaper daemon in the base ISO.
if [ "$(cat "$HOME/.config/abyss/oled-blanking" 2>/dev/null)" = 1 ]; then
    xset s 600 600; xset +dpms; xset dpms 600 600 600
else
    xset s off; xset -dpms
fi

# Restore a saved monitor mode/refresh profile, then enable any new outputs.
command -v abyss-display >/dev/null 2>&1 && abyss-display --restore >/dev/null 2>&1

# Keyboard: us,ara layouts, Alt+Shift toggle, Caps=Escape, Super fix inside VMs
/usr/local/bin/abyss-keyboard

# Index installed desktop apps for the menu; the image ships with no apps.
[ -x /usr/local/bin/abyss-apps ] && /usr/local/bin/abyss-apps --refresh >/dev/null 2>&1 &

# Create standard user folders when the matching Void utility is installed.
command -v xdg-user-dirs-update >/dev/null 2>&1 && xdg-user-dirs-update

# Start optional PipeWire components if the user installed audio support.
if command -v pipewire >/dev/null 2>&1 && ! pgrep -x pipewire >/dev/null 2>&1; then
    pipewire &
fi
if command -v wireplumber >/dev/null 2>&1 && ! pgrep -x wireplumber >/dev/null 2>&1; then
    wireplumber &
fi
if command -v pipewire-pulse >/dev/null 2>&1 && ! pgrep -x pipewire-pulse >/dev/null 2>&1; then
    pipewire-pulse &
fi
/usr/local/bin/dwm-statusbar &

# Set Abyss cosmic background
if command -v feh >/dev/null 2>&1 && [ -f /usr/share/backgrounds/abyss/abyss-wallpaper.jpg ]; then
    feh --bg-fill /usr/share/backgrounds/abyss/abyss-wallpaper.jpg &
else
    xsetroot -solid "#000000" &
fi

# Offer the optional setup window on first login (the user can defer it).
command -v abyss-setup >/dev/null 2>&1 && abyss-setup --first-run &

# Launch dwm (under dbus/elogind session if available)
if command -v dbus-run-session >/dev/null 2>&1 && [ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ]; then
    exec dbus-run-session dwm
else
    exec dwm
fi
