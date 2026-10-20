#!/usr/bin/env bash
# ==============================================================================
# build-distro.sh - Master Void Linux Suckless Developer Workstation ISO Builder
# Builds both ARM64 (aarch64) and x86_64 ISOs (automatically uses QEMU HVF
# Void Linux builder VM when executed on macOS).
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MKLIVE_DIR="${SCRIPT_DIR}/void-mklive"
OVERLAY_DIR="${SCRIPT_DIR}/custom-overlay"
OUTPUT_ISO_AARCH64="${SCRIPT_DIR}/void-suckless-dev-aarch64.iso"
OUTPUT_ISO_X86_64="${SCRIPT_DIR}/void-suckless-dev-x86_64.iso"
OUTPUT_ISO_DEFAULT="${SCRIPT_DIR}/void-suckless-dev.iso"

if [[ ! -d "$MKLIVE_DIR" ]]; then
    echo "Error: void-mklive directory not found at ${MKLIVE_DIR}" >&2
    exit 1
fi

if [[ ! -d "$OVERLAY_DIR" ]]; then
    echo "Error: custom-overlay directory not found at ${OVERLAY_DIR}" >&2
    exit 1
fi

# Package groups
PKGS_BASE_X11="base-system base-devel git curl wget grub grub-arm64-efi grub-x86_64-efi efibootmgr dosfstools parted gdisk xorg-minimal xf86-video-fbdev xf86-input-libinput xinit xsetroot xrandr arandr feh libX11-devel libXft-devel libXinerama-devel mesa-dri vulkan-loader"
PKGS_NET_AUDIO="NetworkManager network-manager-applet pipewire wireplumber pavucontrol dbus elogind polkit dunst libnotify"
PKGS_TERM_CLI="alacritty nerd-fonts-symbols-ttf font-jetbrains-mono-ttf font-firacode vpm vsv eza bat btop fastfetch fzf ripgrep fd jq bash-completion sudo"
PKGS_SSH_TRANSFER="openssh fuse-sshfs rsync filezilla thunar thunar-volman gvfs zenity xclip"
PKGS_BROWSERS_DEV="firefox chromium vscode nodejs python3 python3-pip go rust gcc clang make cmake pkg-config"
PKGS_CONTAINERS_VM_AI="docker docker-compose docker-buildx qemu libvirt virt-manager bridge-utils ollama flatpak"
PKGS_ARTCRAFT="gimp inkscape krita blender darktable"
PKGS_ABYSS="xmenu xdotool sxhkd setxkbmap xrdb xmodmap xev opendoas mpv vim lf rofi dunst file chafa tumbler xdg-user-dirs"
# Abyss builds of the suckless tools from the signed Abyss PMR
ABYSS_PMR="${ABYSS_PMR:-https://mrzakaria.github.io/AbyssLinuxPMR/current}"
PKGS_SUCKLESS="abyss-dwm abyss-st abyss-dmenu abyss-slock abyss-tabbed abyss-wmname abyss-theme"

ALL_PACKAGES="${PKGS_BASE_X11} ${PKGS_NET_AUDIO} ${PKGS_TERM_CLI} ${PKGS_SSH_TRANSFER} ${PKGS_BROWSERS_DEV} ${PKGS_CONTAINERS_VM_AI} ${PKGS_ARTCRAFT} ${PKGS_ABYSS} ${PKGS_SUCKLESS}"
ENABLED_SERVICES="dbus elogind polkit NetworkManager sshd docker libvirtd virtlogd ollama"

# Silent boot (later loglevel= overrides mklive's built-in loglevel=4)
ABYSS_BOOT_CMDLINE="quiet loglevel=3 rd.udev.log_level=3 udev.log_level=3"
ABYSS_POSTSETUP="${SCRIPT_DIR}/builder/abyss-postsetup.sh"
ABYSS_SPLASH="${OVERLAY_DIR}/usr/share/backgrounds/abyss/abyss-splash.png"

echo "=================================================================="
echo "  Building Custom Void Linux Suckless Developer Workstation ISO"
echo "  Target Archs : aarch64 (Apple Silicon / Lumen) + x86_64 (glibc)"
echo "  Overlay      : ${OVERLAY_DIR}"
echo "  Output ISOs  : ${OUTPUT_ISO_AARCH64}"
echo "                 ${OUTPUT_ISO_X86_64}"
echo "=================================================================="

if [[ "$(uname -s)" == "Darwin" ]]; then
    echo "[*] Detected macOS host — running Void Linux mklive inside local QEMU HVF Builder VM..."
    BUILDER_DIR="${BUILDER_DIR:-/tmp/void-builder}"

    if [[ ! -f "${BUILDER_DIR}/vmlinux" || ! -d "${BUILDER_DIR}/rootfs/usr" ]]; then
        echo "[*] Builder VM assets not found in ${BUILDER_DIR}. Provisioning automatically..."
        "${SCRIPT_DIR}/builder/setup-builder.sh" "${BUILDER_DIR}"
    fi

    # Each ISO build needs ~6-8 GB of scratch space inside the sparse disk image.
    FREE_GB=$(df -g /tmp | awk 'NR==2 {print $4}')
    if (( FREE_GB < 12 )); then
        echo "WARNING: only ${FREE_GB} GB free on the host disk; the build may run out of space." >&2
    fi

    # Always use the versioned builder script from the workspace.
    install -m 0755 "${SCRIPT_DIR}/builder/builder.sh" "${BUILDER_DIR}/rootfs/builder.sh"

    echo "[*] Packing ext4 builder disk image (${BUILDER_DIR}/root.ext4)..."
    rm -f "${BUILDER_DIR}/root.ext4"
    /opt/homebrew/bin/mke2fs -q -t ext4 -d "${BUILDER_DIR}/rootfs" "${BUILDER_DIR}/root.ext4" 48G
    trap 'rm -f "${BUILDER_DIR}/root.ext4"' EXIT

    # Unknown KEY=value kernel parameters are passed to init as environment variables.
    VM_ENV="FAST_ISO=${FAST_ISO:-1} FORCE_REBUILD=${FORCE_REBUILD:-0} BUILD_X86_64=${BUILD_X86_64:-1}"

    echo "[*] Booting QEMU HVF Void Linux Builder VM (${VM_ENV})..."
    /opt/homebrew/bin/qemu-system-aarch64 \
        -M virt,accel=hvf \
        -cpu host \
        -smp 8 \
        -m 8G \
        -nographic \
        -kernel "${BUILDER_DIR}/vmlinux" \
        -append "root=/dev/sda rw console=ttyAMA0 init=/builder.sh ${VM_ENV}" \
        -device ich9-ahci,id=ahci \
        -drive file="${BUILDER_DIR}/root.ext4",if=none,id=d0,format=raw \
        -device ide-hd,drive=d0,bus=ahci.0 \
        -netdev user,id=net0 \
        -device virtio-net-pci,netdev=net0 \
        -virtfs local,path="${SCRIPT_DIR}",mount_tag=hostshare,security_model=none,id=hostshare

    ls -lh "${OUTPUT_ISO_AARCH64}" "${OUTPUT_ISO_X86_64}" "${OUTPUT_ISO_DEFAULT}" 2>/dev/null || true
    exit 0
fi

# Work on a copy of void-mklive so the Abyss boot tweaks never touch the
# vendored tree (hidden GRUB menu, ABYSS_LIVE label, abyss-live hostname).
MKLIVE_WORK="$(mktemp -d)"
trap 'sudo rm -rf "$MKLIVE_WORK"' EXIT
cp -a "$MKLIVE_DIR" "$MKLIVE_WORK/"
sh "${SCRIPT_DIR}/builder/abyss-mklive-tweaks.sh" "$MKLIVE_WORK/void-mklive"
cd "$MKLIVE_WORK/void-mklive"

# 1. Build aarch64 ISO
sudo env SPLASH_IMAGE="$ABYSS_SPLASH" ./mklive.sh \
    -a aarch64 \
    -r "$ABYSS_PMR" \
    -c "${MKLIVE_DIR}/xbps-cachedir-aarch64" \
    -i zstd \
    -s zstd \
    -o "$OUTPUT_ISO_AARCH64" \
    -I "$OVERLAY_DIR" \
    -p "${ALL_PACKAGES}" \
    -S "${ENABLED_SERVICES}" \
    -C "$ABYSS_BOOT_CMDLINE" \
    -x "$ABYSS_POSTSETUP" \
    -T "Abyss Linux Suckless Developer Workstation"
cp -f "$OUTPUT_ISO_AARCH64" "$OUTPUT_ISO_DEFAULT"

# 2. Build x86_64 ISO
sudo env SPLASH_IMAGE="$ABYSS_SPLASH" ./mklive.sh \
    -a x86_64 \
    -r "$ABYSS_PMR" \
    -c "${MKLIVE_DIR}/xbps-cachedir-x86_64" \
    -i zstd \
    -s zstd \
    -o "$OUTPUT_ISO_X86_64" \
    -I "$OVERLAY_DIR" \
    -p "${ALL_PACKAGES}" \
    -S "${ENABLED_SERVICES}" \
    -C "$ABYSS_BOOT_CMDLINE" \
    -x "$ABYSS_POSTSETUP" \
    -T "Abyss Linux Suckless Developer Workstation"
