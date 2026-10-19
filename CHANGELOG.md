# Changelog

## v27.0 (2026-10-20): first public release

ISOs: `abyss-linux-27.0-aarch64.iso`, `abyss-linux-27.0-x86_64.iso`

### Base
* Void Linux (glibc, rolling) with kernel 6.18.57, runit, XBPS 0.60.7, dracut 112, GRUB 2.12.
* Silent boot: hidden GRUB menu (2 s; Esc/Shift to show), `quiet loglevel=3`, Abyss splash.
* ISO label `ABYSS_LIVE`, live hostname `abyss-live`, `/etc/os-release` reports `VERSION_ID="27.0"`.

### Abyss Linux PMR
* The suckless tools ship as signed packages from the [Abyss PMR](https://github.com/MrZaKaRiA/AbyssLinuxPMR): `abyss-dwm` 6.8_1, `abyss-st` 0.9.3_1, `abyss-dmenu` 5.4_1, `abyss-slock` 1.7_1, `abyss-tabbed` 0.9_1, `abyss-wmname` 0.1_1.
* `/etc/xbps.d/20-abyss-pmr.conf` and the signing key are preinstalled, so `xbps-install -Su` updates them.

### Desktop
* dwm with systray, status2d, vanitygaps, scratchpad, attachaside and autostart, in the Abyss purple theme.
* A minimal status bar (CPU, RAM, clock, offline warning) and a **Menu** button: one click opens the Abyss menu (xmenu).
* HiDPI: automatic `Xft.dpi` (2× in Apple Virtualization and on ≥1700 px screens, 1.5× from 1300 px). st uses point sizes so it scales too.
* The NetworkManager tray icon is opt-in (Menu → System settings).
* New basic apps: mpv, vim (default `$EDITOR` without VS Code), lf with previews, rofi launcher (`Super+Alt+r`), dunst notifications. All themed.
* sxhkd hotkeys on `Super+Alt+<letter>` and media keys; `Super+F1` cheatsheet.

### Installer
* Menu → **Install Abyss Linux** opens `void-installer` in a large st window.
* Dark, high-contrast dialog theme (`/etc/dialogrc`); title "Abyss Linux installer (27.0)".
* One-step automatic UEFI partitioning (GPT, 1 GB ESP, ext4 root) and a removable `EFI/BOOT` fallback.
* Fixed: the installed system's tty1 looped "User not known to the underlying authentication module" (the live autologin user was deleted but still configured). It now shows a normal login prompt, and the desktop starts after login.
* Fixed: removing `dialog` from the target failed because `xmirror` still depended on it.

### Build
* `build-distro.sh` builds both ISOs on macOS (QEMU + HVF builder VM) or natively on Void.
* The builder unlinks the old ISO before writing the new one, so a VM that has it open is not corrupted.
