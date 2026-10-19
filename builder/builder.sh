#!/bin/bash
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

mount -t proc proc /proc
mount -t sysfs sys /sys
mount -t devtmpfs dev /dev
mkdir -p /dev/pts /dev/shm /run /tmp /workspace
mount -t devpts devpts /dev/pts
mount -t tmpfs tmpfs /run
mount -t tmpfs tmpfs /tmp

KVER=$(ls /usr/lib/modules | head -n1)
depmod -a "$KVER" 2>/dev/null || true

for mod in virtio_pci virtio_net virtio_blk 9pnet 9pnet_virtio 9p loop squashfs overlay isofs vfat fat nls_cp437 nls_iso8859_1 binfmt_misc; do
    modprobe "$mod" 2>/dev/null || true
done

ip link set lo up
for iface in /sys/class/net/*; do
    ifname=$(basename "$iface")
    [ "$ifname" = "lo" ] && continue
    ip link set "$ifname" up
    ip addr add 10.0.2.15/24 dev "$ifname" 2>/dev/null || true
    ip route add default via 10.0.2.2 dev "$ifname" 2>/dev/null || true
done
echo "nameserver 1.1.1.1" > /etc/resolv.conf
echo "nameserver 8.8.8.8" >> /etc/resolv.conf

mount -t 9p -o trans=virtio,version=9p2000.L,msize=104857600 hostshare /workspace

echo "=== Synchronizing Builder Packages ==="
xbps-install -Sy -u xbps || true
xbps-install -Sy -u bash coreutils util-linux gawk sed grep findutils squashfs-tools xorriso grub-arm64-efi zstd || true
xbps-install -Sy -u qemu-user-static || xbps-install -Sy -u qemu-user || true
xbps-install -Sy -u binfmt-support || true

if [ -x /usr/bin/qemu-x86_64-static ] && [ ! -e /usr/bin/qemu-x86_64 ]; then
    ln -sf /usr/bin/qemu-x86_64-static /usr/bin/qemu-x86_64
elif [ -x /usr/bin/qemu-x86_64 ] && [ ! -e /usr/bin/qemu-x86_64-static ]; then
    ln -sf /usr/bin/qemu-x86_64 /usr/bin/qemu-x86_64-static
fi

mount -t binfmt_misc binfmt_misc /proc/sys/fs/binfmt_misc 2>/dev/null || true
if [ -w /proc/sys/fs/binfmt_misc/register ] && [ ! -f /proc/sys/fs/binfmt_misc/qemu-x86_64 ]; then
    QBIN="/usr/bin/qemu-x86_64-static"
    [ ! -x "$QBIN" ] && QBIN="/usr/bin/qemu-x86_64"
    echo ":qemu-x86_64:M::\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x3e\x00:\xff\xff\xff\xff\xff\xfe\xfe\x00\xff\xff\xff\xff\xff\xff\xff\xff\xfe\xff\xff\xff:${QBIN}:CF" > /proc/sys/fs/binfmt_misc/register 2>/dev/null || true
fi
ls -l /proc/sys/fs/binfmt_misc/ 2>/dev/null || true

mkdir -p /build
cp -a /workspace/void-mklive /build/
# Abyss boot/branding tweaks on the working copy only (quiet hidden GRUB menu,
# ABYSS_LIVE label, abyss-live hostname, Abyss PMR signing key)
sh /workspace/builder/abyss-mklive-tweaks.sh /build/void-mklive
# One overlay for both architectures: the suckless binaries come from the PMR
cp -a /workspace/custom-overlay /build/overlay

cd /build/void-mklive

PKGS_INSTALLER="dialog parted gdisk cryptsetup lvm2 mdadm xtools-minimal xmirror dosfstools efibootmgr grub grub-arm64-efi"
PKGS_INPUT="xf86-input-libinput xf86-input-evdev xorg-input-drivers"
# Abyss menu (xmenu + xdotool), hotkeys, keyboard tools, doas, basic apps
# (mpv player, vim editor, lf file manager + previews, rofi launcher, dunst)
PKGS_ABYSS="xmenu xdotool sxhkd setxkbmap xrdb xmodmap xev opendoas mpv vim lf rofi dunst file chafa"
# Abyss builds of the suckless tools, from the signed Abyss PMR
# (https://github.com/MrZaKaRiA/AbyssLinuxPMR); they replace Void's st/dwm/dmenu
ABYSS_PMR="${ABYSS_PMR:-https://mrzakaria.github.io/AbyssLinuxPMR/current}"
PKGS_SUCKLESS="abyss-dwm abyss-st abyss-dmenu abyss-slock abyss-tabbed abyss-wmname"

# Silent boot (later loglevel= overrides mklive's built-in loglevel=4)
ABYSS_BOOT_CMDLINE="quiet loglevel=3 rd.udev.log_level=3 udev.log_level=3"
ABYSS_POSTSETUP=/workspace/builder/abyss-postsetup.sh
# Abyss GRUB background instead of Void's data/splash.png
export SPLASH_IMAGE=/workspace/custom-overlay/usr/share/backgrounds/abyss/abyss-splash.png

PKGS_CORE="base-system base-devel git curl wget xorg-minimal xf86-video-fbdev ${PKGS_INPUT} ${PKGS_INSTALLER} ${PKGS_ABYSS} xinit xsetroot xrandr arandr pavucontrol feh libX11-devel libXft-devel libXinerama-devel mesa-dri vulkan-loader NetworkManager network-manager-applet pipewire wireplumber dbus elogind polkit dunst libnotify ${PKGS_SUCKLESS} alacritty nerd-fonts-symbols-ttf font-firacode dejavu-fonts-ttf vpm vsv eza bat btop fastfetch fzf ripgrep fd jq bash-completion sudo openssh fuse-sshfs rsync filezilla Thunar thunar-volman gvfs zenity xclip firefox chromium vscode nodejs python3 python3-pip go gcc clang make cmake pkg-config docker docker-compose docker-buildx qemu libvirt virt-manager bridge-utils ollama flatpak gimp inkscape krita blender darktable"
SERVICES="dbus elogind polkit NetworkManager sshd docker libvirtd virtlogd ollama"

if [ "${FAST_ISO:-1}" = "1" ]; then
    PKGS_BUILD="base-system git curl wget xorg-minimal xf86-video-fbdev ${PKGS_INPUT} ${PKGS_INSTALLER} ${PKGS_ABYSS} xinit xsetroot xrandr arandr pavucontrol feh mesa-dri NetworkManager network-manager-applet pipewire wireplumber dbus elogind polkit dunst libnotify ${PKGS_SUCKLESS} alacritty nerd-fonts-symbols-ttf font-firacode dejavu-fonts-ttf eza bat btop fastfetch fzf ripgrep fd jq bash-completion sudo openssh fuse-sshfs rsync Thunar zenity xclip"
    SERVICES_BUILD="dbus elogind polkit NetworkManager sshd ollama"
else
    PKGS_BUILD="$PKGS_CORE"
    SERVICES_BUILD="$SERVICES"
fi

if [ ! -f /workspace/void-suckless-dev-aarch64.iso ] || [ "${FORCE_REBUILD:-0}" = "1" ]; then
    echo "=== [1/2] Building ARM64 (aarch64) ISO for Apple Silicon / Lumen.app ==="
    if ./mklive.sh \
        -a aarch64 \
        -r "$ABYSS_PMR" \
        -i gzip \
        -s zstd \
        -o /build/void-suckless-dev-aarch64.iso \
        -I /build/overlay \
        -p "$PKGS_BUILD" \
        -S "$SERVICES_BUILD" \
        -C "$ABYSS_BOOT_CMDLINE" \
        -x "$ABYSS_POSTSETUP" \
        -T "Abyss Linux Suckless Developer Workstation"; then

        # unlink first: a VM that has the old ISO open keeps reading the old file
        rm -f /workspace/void-suckless-dev-aarch64.iso
        cp -f /build/void-suckless-dev-aarch64.iso /workspace/void-suckless-dev-aarch64.iso
        rm -f /workspace/void-suckless-dev.iso
        ln /workspace/void-suckless-dev-aarch64.iso /workspace/void-suckless-dev.iso 2>/dev/null || \
            cp -f /workspace/void-suckless-dev-aarch64.iso /workspace/void-suckless-dev.iso
        echo "✅ Saved void-suckless-dev-aarch64.iso and void-suckless-dev.iso"
    else
        echo "❌ Failed to build ARM64 ISO"
    fi
else
    echo "=== [1/2] void-suckless-dev-aarch64.iso already exists, skipping to x86_64 build ==="
fi

if [ "${BUILD_X86_64:-1}" = "1" ] && { [ ! -f /workspace/void-suckless-dev-x86_64.iso ] || [ "${FORCE_REBUILD:-0}" = "1" ]; }; then
    echo "=== [2/2] Building x86_64 ISO ==="
    ./mklive.sh \
        -a x86_64 \
        -r "$ABYSS_PMR" \
        -i gzip \
        -s zstd \
        -o /build/void-suckless-dev-x86_64.iso \
        -I /build/overlay \
        -p "${PKGS_BUILD//grub-arm64-efi/grub-x86_64-efi}" \
        -S "$SERVICES_BUILD" \
        -C "$ABYSS_BOOT_CMDLINE" \
        -x "$ABYSS_POSTSETUP" \
        -T "Abyss Linux Suckless Developer Workstation"
    # unlink first: a VM that has the old ISO open keeps reading the old file
    rm -f /workspace/void-suckless-dev-x86_64.iso
    cp -f /build/void-suckless-dev-x86_64.iso /workspace/void-suckless-dev-x86_64.iso
    echo "✅ Saved void-suckless-dev-x86_64.iso"
fi

sync
poweroff -f
