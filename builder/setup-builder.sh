#!/usr/bin/env bash
# ==============================================================================
# setup-builder.sh - Auto-provisions the Void Linux builder VM environment
# ==============================================================================

set -euo pipefail

BUILDER_DIR="${1:-${BUILDER_DIR:-/tmp/void-builder}}"
export BUILDER_DIR

if [[ -f "${BUILDER_DIR}/vmlinux" && -d "${BUILDER_DIR}/rootfs/usr" ]]; then
    echo "[*] Builder VM assets already exist at ${BUILDER_DIR}"
    exit 0
fi

echo "[*] Setting up Void Linux builder VM assets at ${BUILDER_DIR}..."
mkdir -p "${BUILDER_DIR}"

TMP_PLIST="${BUILDER_DIR}/index.plist"
if [[ ! -f "$TMP_PLIST" ]]; then
    echo "[*] Downloading package repository metadata..."
    curl -sL https://repo-default.voidlinux.org/current/aarch64/aarch64-repodata | tar --zstd -xf - -C "${BUILDER_DIR}" index.plist
fi

python3 - << 'EOF'
import plistlib, urllib.request, os, sys

builder_dir = os.environ.get("BUILDER_DIR", "/tmp/void-builder")
plist_path = os.path.join(builder_dir, "index.plist")

with open(plist_path, "rb") as f:
    data = plistlib.load(f)

linux_meta = data["linux"]
kpkg = [d.split(">=")[0] for d in linux_meta["run_depends"] if d.startswith("linux6")][0]
kinfo = data[kpkg]
kfname = f"{kinfo['pkgver']}.aarch64.xbps"

packages = [
    ("rootfs.tar.xz", "https://repo-default.voidlinux.org/live/current/void-aarch64-ROOTFS-20250202.tar.xz"),
    ("kernel.xbps", f"https://repo-default.voidlinux.org/current/aarch64/{kfname}"),
    ("e2fsprogs.xbps", f"https://repo-default.voidlinux.org/current/aarch64/{data['e2fsprogs']['pkgver']}.aarch64.xbps"),
    ("dosfstools.xbps", f"https://repo-default.voidlinux.org/current/aarch64/{data['dosfstools']['pkgver']}.aarch64.xbps"),
]

for name, url in packages:
    dest = os.path.join(builder_dir, name)
    if not os.path.exists(dest):
        print(f"[*] Downloading {name}...")
        urllib.request.urlretrieve(url, dest)
print("[✓] All builder downloads finished.")
EOF

echo "[*] Extracting builder rootfs..."
mkdir -p "${BUILDER_DIR}/rootfs"
for archive in rootfs.tar.xz kernel.xbps e2fsprogs.xbps dosfstools.xbps; do
    echo "    Extracting ${archive}..."
    tar -xf "${BUILDER_DIR}/${archive}" -C "${BUILDER_DIR}/rootfs"
done

cp "${BUILDER_DIR}/rootfs"/boot/vmlinux-* "${BUILDER_DIR}/vmlinux"
echo "[✓] Builder VM environment ready at ${BUILDER_DIR}/vmlinux"
