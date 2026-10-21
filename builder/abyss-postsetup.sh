#!/bin/sh
# ==============================================================================
# abyss-postsetup.sh <rootfs>   (passed to void-mklive with -x)
#
# mklive copies the overlay with `cp -p`, which keeps the *builder's* file
# owner (uid 501 from the macOS 9p share). This hook runs inside the build,
# after the overlay copy, and normalises every overlay path:
#   owner root:root, scripts 0755, /etc/doas.conf 0400, no .DS_Store files.
# ==============================================================================
set -eu

ROOTFS="${1:?usage: $0 <rootfs>}"
OVERLAY="${ABYSS_OVERLAY:-$(cd "$(dirname "$0")/../custom-overlay" && pwd)}"

[ -d "$OVERLAY" ] || { echo "abyss-postsetup: overlay $OVERLAY not found" >&2; exit 1; }

# macOS Finder metadata never belongs in the image
find "$ROOTFS" -xdev -name .DS_Store -type f -delete 2>/dev/null || true

# Ownership: only paths that come from the overlay (never chown package dirs)
( cd "$OVERLAY" && find . -mindepth 1 ! -name .DS_Store ! -path './usr/local/bin-*' ) |
while IFS= read -r p; do
    t="$ROOTFS/${p#./}"
    if [ -e "$t" ] || [ -L "$t" ]; then
        chown -h root:root "$t"
    fi
done

# Permissions
for f in "$ROOTFS"/usr/local/bin/* "$ROOTFS"/usr/bin/void-installer \
         "$ROOTFS"/etc/skel/.xinitrc "$ROOTFS"/etc/skel/.dwm/autostart.sh "$ROOTFS"/etc/skel/.config/lf/preview \
         "$ROOTFS"/etc/sv/ollama/run "$ROOTFS"/etc/sv/polkit/run; do
    [ -f "$f" ] && chmod 0755 "$f"
done
for f in "$ROOTFS"/etc/rc.conf "$ROOTFS"/etc/default/grub "$ROOTFS"/etc/dialogrc "$ROOTFS"/etc/X11/xorg.conf.d/*.conf; do
    [ -f "$f" ] && chmod 0644 "$f"
done
# doas refuses a config that others can write; keep it root-only
# Boot splash and login screen: plain readable files (the greeter runs as the
# lightdm user, plymouth reads its theme while building the initramfs)
for f in "$ROOTFS"/etc/lightdm/*.conf "$ROOTFS"/etc/lightdm/.session "$ROOTFS"/etc/lightdm/lightdm.conf.d/*.conf \
         "$ROOTFS"/etc/plymouth/plymouthd.conf "$ROOTFS"/etc/dracut.conf.d/40-abyss-plymouth.conf \
         "$ROOTFS"/usr/share/xsessions/abyss.desktop "$ROOTFS"/usr/share/plymouth/themes/abyss/*; do
    [ -f "$f" ] && chmod 0644 "$f"
done
[ -f "$ROOTFS/etc/doas.conf" ] && chmod 0400 "$ROOTFS/etc/doas.conf"
# sudo ignores drop-ins that are not 0440 root:root
[ -f "$ROOTFS/etc/sudoers.d/abyss-power" ] && chmod 0440 "$ROOTFS/etc/sudoers.d/abyss-power"
[ -f "$ROOTFS/etc/runit/core-services/11-abyss-runit-ctl.sh" ] && chmod 0644 "$ROOTFS/etc/runit/core-services/11-abyss-runit-ctl.sh"

# Release version: $ABYSS_VERSION, else the repository's VERSION file, else the date
VERSION_FILE="$(dirname "$0")/../VERSION"
if [ -z "${ABYSS_VERSION:-}" ] && [ -r "$VERSION_FILE" ]; then
    ABYSS_VERSION="$(tr -d ' \n' < "$VERSION_FILE")"
fi
ABYSS_VERSION="${ABYSS_VERSION:-$(date +%Y.%m.%d)}"

# Installer title (mkiso.sh would do this, but mklive.sh does not)
if [ -f "$ROOTFS/usr/bin/void-installer" ]; then
    sed -i "s/@@MKLIVE_VERSION@@/${ABYSS_VERSION}/g" "$ROOTFS/usr/bin/void-installer"
fi

# /etc/os-release: VERSION, VERSION_ID and BUILD_ID for this build
OSR="$ROOTFS/etc/os-release"
[ -L "$OSR" ] && OSR="$ROOTFS/usr/lib/os-release"
if [ -f "$OSR" ]; then
    sed -i -e '/^VERSION=/d' -e '/^VERSION_ID=/d' -e '/^BUILD_ID=/d' "$OSR"
    printf 'VERSION="%s"\nVERSION_ID="%s"\nBUILD_ID="%s"\n' \
        "$ABYSS_VERSION" "$ABYSS_VERSION" "$(date +%Y%m%d)" >> "$OSR"
fi
echo "[abyss] version $ABYSS_VERSION"

# Report (not fatal) what the Abyss desktop scripts expect to find
missing=""
for c in dwm st dmenu slock tabbed wmname xmenu xdotool sxhkd setxkbmap xrdb xmodmap xev doas rofi lf vim mpv dunst plymouth lightdm lightdm-gtk-greeter; do
    [ -x "$ROOTFS/usr/bin/$c" ] || missing="$missing $c"
done
[ -n "$missing" ] && echo "[abyss] WARNING: not in image:$missing (menu/keyboard fall back where possible)"
echo "[abyss] overlay ownership and permissions normalised"
