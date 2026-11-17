#!/bin/bash
# Inspect the actual installed files inside a live ISO, not just its filename.
set -euo pipefail
iso=${1:?usage: audit-iso.sh path/to/image.iso}
work=$(mktemp -d /tmp/abyss-iso-audit.XXXXXX)
cleanup() {
    mountpoint -q "$work/root" && umount "$work/root" || true
    rm -rf "$work"
}
trap cleanup EXIT
mkdir -p "$work/root"
xorriso -osirrox on -indev "$iso" -extract /LiveOS/squashfs.img "$work/squashfs.img"
unsquashfs -no-progress -d "$work/squash" "$work/squashfs.img" LiveOS/rootfs.img
mount -o loop,ro "$work/squash/LiveOS/rootfs.img" "$work/root"
for package in abyss-dwm abyss-desktop abyss-st abyss-dmenu nsxiv feh xss-lock xmenu xdotool xbps; do
    xbps-query -r "$work/root" -p pkgver "$package"
done
grep -q 'repository=https://mrzakaria.github.io/AbyssLinuxPMR/current' "$work/root/etc/xbps.d/20-abyss-pmr.conf"
test -x "$work/root/usr/bin/abyss-key-capture"
test -x "$work/root/usr/bin/abyss-cursor"
test -x "$work/root/usr/bin/abyss-wallpaper"
test -x "$work/root/usr/bin/abyss-wallpapers"
test -f "$work/root/usr/share/backgrounds/abyss/abyss-wallpaper.jpg"
test -d "$work/root/usr/share/icons/Adwaita/cursors"
test -x "$work/root/usr/local/bin/abyss-file-chooser-init"
test -x "$work/root/usr/local/bin/abyss-rofi-repair"
test -x "$work/root/usr/local/bin/abyss-thunar-init"
grep -Fq 'ADW_DEBUG_COLOR_SCHEME' "$work/root/usr/local/bin/abyss-session"
grep -Fq '.thunar .shortcuts-pane' "$work/root/usr/share/themes/Abyss/gtk-3.0/gtk.css"
test -x "$work/root/usr/bin/img"
test ! -L "$work/root/usr/local/bin/abyss-welcome"
test -f "$work/root/etc/skel/.config/rofi/config.rasi"
if grep -q '^}\";' "$work/root/etc/skel/.config/rofi/config.rasi"; then
    echo 'Broken rofi configuration terminator found' >&2
    exit 1
fi
version=$(tr -d ' \n' < "$(dirname "$0")/../VERSION")
grep -Fx "VERSION_ID=\"$version\"" "$work/root/usr/lib/os-release"
grep -q 'Text size: automatic' "$work/root/usr/local/bin/abyss-control-center"
xbps-query -r "$work/root" -p pkgver abyss-desktop | grep -Fx 'abyss-desktop-1.0_28'
xbps-query -r "$work/root" -p pkgver abyss-slock | grep -Fx 'abyss-slock-1.7_2'
xbps-query -r "$work/root" -p pkgver abyss-st | grep -Fx 'abyss-st-0.9.3_2'
xbps-query -r "$work/root" -p pkgver abyss-dwm | grep -Fx 'abyss-dwm-6.8_9'
test -x "$work/root/usr/bin/abyss-record"
test -f "$work/root/etc/skel/.config/zathura/zathurarc"
test -f "$work/root/etc/skel/.vim/ftplugin/tex.vim"
xbps-query -r "$work/root" -p pkgver abyss-theme | grep -Fx 'abyss-theme-1.0_4'
# Ownership and modes that break logins or privilege escalation when wrong
lightdm_ids=$(awk -F: '$1 == "lightdm" {print $3 ":" $4}' "$work/root/etc/passwd")
test -n "$lightdm_ids"
if [ "$(stat -c '%u:%g' "$work/root/var/lib/lightdm")" != "$lightdm_ids" ]; then
    echo "/var/lib/lightdm is not owned by lightdm ($lightdm_ids)" >&2
    exit 1
fi
if [ -e "$work/root/etc/doas.conf" ] && [ "$(stat -c '%a %u:%g' "$work/root/etc/doas.conf")" != '400 0:0' ]; then
    echo '/etc/doas.conf is not mode 0400 root:root' >&2
    exit 1
fi
if [ -e "$work/root/etc/sudoers.d/abyss-power" ] && [ "$(stat -c '%a %u:%g' "$work/root/etc/sudoers.d/abyss-power")" != '440 0:0' ]; then
    echo '/etc/sudoers.d/abyss-power is not mode 0440 root:root' >&2
    exit 1
fi
echo 'Installed packages and overlay: PASS'
