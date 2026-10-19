#!/bin/sh
# ==============================================================================
# abyss-mklive-tweaks.sh <mklive-dir>
# Applies Abyss boot-screen tweaks to a *working copy* of void-mklive before
# mklive.sh runs. The vendored ./void-mklive tree is never modified.
#   - live GRUB menu hidden (hold Esc/Shift to show it), 2 s timeout
#   - ISO volume label ABYSS_LIVE instead of VOID_LIVE
#   - live hostname abyss-live instead of void-live
#   - Abyss PMR signing key added to keys/ (trusted repository)
# The GRUB background comes from SPLASH_IMAGE (exported by the build scripts).
# The kernel side of the silent boot comes from ABYSS_BOOT_CMDLINE (mklive -C).
# Idempotent: safe to run more than once.
# ==============================================================================
set -eu

MK="${1:?usage: $0 <mklive-dir>}"
PRE="$MK/grub/grub_void.cfg.pre"

[ -f "$PRE" ] || { echo "abyss-mklive-tweaks: $PRE not found" >&2; exit 1; }

sed -i \
    -e 's/^timeout=[0-9]*$/timeout=2/' \
    -e 's/^timeout_style=.*/timeout_style=hidden/' \
    "$PRE"

grep -q '^timeout_style=hidden' "$PRE" || { echo "abyss-mklive-tweaks: could not set hidden menu" >&2; exit 1; }
echo "[abyss] live GRUB menu: hidden, timeout 2s"

# Volume label: GRUB root=live:CDLABEL=..., xorriso -volid, isolinux entries
for f in "$MK/mklive.sh" "$MK/isolinux/isolinux.cfg.in"; do
    [ -f "$f" ] && sed -i 's/VOID_LIVE/ABYSS_LIVE/g' "$f"
done
echo "[abyss] ISO volume label: ABYSS_LIVE"

# Live hostname written by the dracut live hook
ADDUSER="$MK/dracut/vmklive/adduser.sh"
[ -f "$ADDUSER" ] && sed -i 's/^echo void-live > /echo abyss-live > /' "$ADDUSER"
echo "[abyss] live hostname: abyss-live"

# Abyss PMR signing key: mklive copies keys/*.plist into the image, so xbps
# trusts the Abyss repository at build time and on the installed system
KEYDIR="$(cd "$(dirname "$0")/../keys" && pwd)"
if [ -f "$KEYDIR/abyss-pmr.plist" ] && [ -f "$KEYDIR/FINGERPRINT" ]; then
    cp -f "$KEYDIR/abyss-pmr.plist" "$MK/keys/$(cat "$KEYDIR/FINGERPRINT").plist"
    echo "[abyss] PMR signing key: $(cat "$KEYDIR/FINGERPRINT")"
else
    echo "abyss-mklive-tweaks: $KEYDIR/abyss-pmr.plist missing" >&2; exit 1
fi
