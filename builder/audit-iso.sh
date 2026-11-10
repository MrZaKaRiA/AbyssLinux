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
for package in abyss-dwm abyss-desktop abyss-st abyss-dmenu nsxiv xbps; do
    xbps-query -r "$work/root" -p pkgver "$package"
done
grep -q 'repository=https://mrzakaria.github.io/AbyssLinuxPMR/current' "$work/root/etc/xbps.d/20-abyss-pmr.conf"
test -x "$work/root/usr/bin/abyss-key-capture"
test -x "$work/root/usr/local/bin/abyss-file-chooser-init"
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
xbps-query -r "$work/root" -p pkgver abyss-desktop | grep -Fx 'abyss-desktop-1.0_21'
xbps-query -r "$work/root" -p pkgver abyss-theme | grep -Fx 'abyss-theme-1.0_4'
echo 'Installed packages and overlay: PASS'
