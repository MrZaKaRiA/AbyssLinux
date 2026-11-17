#!/bin/bash
# Build a single architecture inside Void's privileged void-mklive container.
set -euo pipefail
arch=${1:?usage: build-one-ci.sh aarch64\|x86_64}
case "$arch" in
    aarch64) grub_efi=grub-arm64-efi ;;
    x86_64) grub_efi=grub-x86_64-efi ;;
    *) echo "Unsupported architecture: $arch" >&2; exit 2 ;;
esac
root=$(cd "$(dirname "$0")/.." && pwd)
version=$(tr -d ' \n' < "$root/VERSION")
work=$(mktemp -d /tmp/abyss-mklive.XXXXXX)
trap 'rm -rf "$work"' EXIT
cp -a "$root/void-mklive" "$work/void-mklive"
sh "$root/builder/abyss-mklive-tweaks.sh" "$work/void-mklive"
mkdir -p "$root/out"
export SPLASH_IMAGE="$root/custom-overlay/usr/share/backgrounds/abyss/abyss-splash.png"
export DEFAULT_SERVICE_LIST='agetty-tty2 agetty-tty3 agetty-tty4 agetty-tty5 agetty-tty6 udevd'
export ABYSS_OVERLAY="$root/custom-overlay"
packages="base-system curl ca-certificates xorg-minimal xss-lock xf86-video-fbdev xf86-input-libinput xf86-input-evdev xorg-input-drivers dialog parted gptfdisk cryptsetup lvm2 mdadm xtools-minimal xmirror dosfstools efibootmgr grub $grub_efi setxkbmap xrdb xmodmap xev opendoas lightdm lightdm-gtk-greeter xinit xsetroot xset xrandr mesa-dri dbus elogind polkit NetworkManager abyss-dwm abyss-st abyss-dmenu abyss-slock abyss-tabbed abyss-wmname abyss-theme nsxiv feh xmenu xdotool font-jetbrains-mono-ttf nerd-fonts-symbols-ttf"
cd "$work/void-mklive"
# elogind is installed but not enabled: D-Bus starts it on demand. Enabling its
# runit service made runit retry every second forever ("already running").
./mklive.sh -a "$arch" -r 'https://mrzakaria.github.io/AbyssLinuxPMR/current' \
    -i gzip -s zstd -o "$root/out/abyss-linux-${version}-${arch}.iso" \
    -I "$root/custom-overlay" -p "$packages" \
    -S 'dbus polkit NetworkManager lightdm' \
    -C 'quiet loglevel=3 rd.udev.log_level=3 udev.log_level=3 vt.global_cursor_default=0' \
    -x "$root/builder/abyss-postsetup.sh" -T 'Abyss Linux Minimal Suckless Desktop'
test -s "$root/out/abyss-linux-${version}-${arch}.iso"
