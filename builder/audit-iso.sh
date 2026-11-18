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
test -f "$work/root/usr/share/backgrounds/abyss/abyss-orbit.jpg"
test -f "$work/root/usr/share/backgrounds/abyss/abyss-wallpaper.jpg"
test -d "$work/root/usr/share/icons/Adwaita/cursors"
test -x "$work/root/usr/local/bin/abyss-file-chooser-init"
test -x "$work/root/usr/local/bin/abyss-rofi-repair"
test -x "$work/root/usr/local/bin/abyss-thunar-init"
grep -Fq 'ADW_DEBUG_COLOR_SCHEME' "$work/root/usr/bin/abyss-session"
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
grep -q 'Text size: automatic' "$work/root/usr/bin/abyss-control-center"
xbps-query -r "$work/root" -p pkgver abyss-desktop | grep -Fx 'abyss-desktop-1.0_33'
xbps-query -r "$work/root" -p pkgver abyss-slock | grep -Fx 'abyss-slock-1.7_2'
xbps-query -r "$work/root" -p pkgver abyss-st | grep -Fx 'abyss-st-0.9.3_2'
xbps-query -r "$work/root" -p pkgver abyss-dwm | grep -Fx 'abyss-dwm-6.8_10'
test -x "$work/root/usr/bin/abyss-record"
test -f "$work/root/etc/skel/.config/zathura/zathurarc"
test -f "$work/root/etc/skel/.vim/ftplugin/tex.vim"
xbps-query -r "$work/root" -p pkgver abyss-theme | grep -Fx 'abyss-theme-1.0_6'
# Shell helpers come from the package (so updates reach installed systems),
# never from an image-only copy
xbps-query -r "$work/root" -o /etc/profile.d/zz-abyss-cli.sh | grep -q '^abyss-desktop-'
test ! -e "$work/root/etc/profile.d/99-void-dev-cli.sh"
grep -Fq '. /etc/profile.d/zz-abyss-cli.sh' "$work/root/etc/skel/.bashrc"
# elogind: installed, started by D-Bus; a runit service for it restart-loops
xbps-query -r "$work/root" -p pkgver elogind
test -f "$work/root/usr/share/dbus-1/system-services/org.freedesktop.login1.service"
if [ -e "$work/root/etc/runit/runsvdir/default/elogind" ] || [ -L "$work/root/etc/runit/runsvdir/default/elogind" ]; then
    echo 'elogind is enabled as a runit service (it must be left to D-Bus activation)' >&2
    exit 1
fi
for sv in dbus polkit NetworkManager lightdm chronyd; do
    test -L "$work/root/etc/runit/runsvdir/default/$sv"
done
# Time synchronisation: chrony enabled (installed systems inherit the link),
# with abyss-desktop's configuration and the once-per-system stamp, so a
# user who disables it later is not overruled by an update
xbps-query -r "$work/root" -p pkgver chrony
test -f "$work/root/etc/sv/chronyd/run"
grep -Fq 'OPTS="-f /usr/share/abyss/chrony.conf"' "$work/root/etc/sv/chronyd/conf"
grep -Fxq 'include /etc/chrony.conf' "$work/root/usr/share/abyss/chrony.conf"
test -f "$work/root/var/lib/abyss-desktop/time-sync-enabled"
# /usr/local/bin: every abyss-desktop command is the managed wrapper, exactly
# what INSTALL leaves on an updated system, never a full copy that shadows
# the package; nothing else is there but the void-installer link
wrappers="$work/root/usr/libexec/abyss-desktop/local-bin-wrappers"
commands=$(sh "$wrappers" --list)
test -n "$commands"
for cmd in $commands; do
    if ! sh "$wrappers" --print "$cmd" | cmp -s - "$work/root/usr/local/bin/$cmd" ||
        [ "$(stat -c '%a %u:%g' "$work/root/usr/local/bin/$cmd")" != '755 0:0' ]; then
        echo "/usr/local/bin/$cmd is not the abyss-desktop wrapper (755 root:root)" >&2
        exit 1
    fi
done
for f in "$work/root"/usr/local/bin/* "$work/root"/usr/local/bin/.[!.]*; do
    [ -e "$f" ] || [ -L "$f" ] || continue
    case " $(printf '%s ' $commands)void-installer " in
        *" ${f##*/} "*) ;;
        *) echo "unexpected /usr/local/bin/${f##*/} in the image" >&2; exit 1 ;;
    esac
done
test "$(readlink "$work/root/usr/local/bin/void-installer")" = /usr/bin/void-installer
# The overlay must not replace files abyss-desktop ships (updates fix those)
overlay="$(dirname "$0")/../custom-overlay"
while read -r f; do
    if [ -e "$overlay$f" ] || [ -L "$overlay$f" ]; then
        echo "custom-overlay$f replaces a file of abyss-desktop" >&2
        exit 1
    fi
done < <(xbps-query -r "$work/root" -f abyss-desktop | sed 's/ -> .*//')
# Installer: Abyss EFI boot entry, and the UTF-8 locale dialog falls back to
# (glibc's built-in C.UTF-8 needs glibc >= 2.35)
inst="$work/root/usr/bin/void-installer"
grep -Fxq 'EFI_BOOTLOADER_ID=Abyss' "$inst"
if grep -v '^[[:space:]]*#' "$inst" | grep -q 'void_grub'; then
    echo 'void-installer still installs GRUB as void_grub' >&2
    exit 1
fi
grep -q 'export LC_CTYPE=' "$inst"
glibc=$(xbps-query -r "$work/root" -p pkgver glibc)
if [ "$(printf '%s\n' glibc-2.35 "$glibc" | sort -V | head -n 1)" != glibc-2.35 ]; then
    echo "$glibc has no built-in C.UTF-8 locale (needs 2.35 or later)" >&2
    exit 1
fi
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
