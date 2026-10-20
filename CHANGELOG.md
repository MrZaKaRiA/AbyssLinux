# Changelog

## Updates since v27.0 (delivered through the Abyss PMR: `sudo xbps-install -Su`)

* **abyss-theme 1.0_1 (new):** Thunar and other GTK apps are no longer white. The "Abyss" GTK 3 theme (Adwaita dark with the Abyss palette) and the "Abyss" icon theme (Papirus-Dark with violet folders) are now the system-wide default.
* **abyss-dwm 6.8_3:** move windows from the keyboard. `Super+Shift+j/k` (or `Shift+↓/↑`) moves the window down/up the stack (movestack), `Super+←/→` switches to the previous/next desktop, and `Super+Shift+←/→` carries the window there. The arrow keys also avoid macOS's `Cmd+Shift+3/4/5` screenshot shortcuts. abyss-dwm now pulls in abyss-theme.
* New ISOs: `tumbler` (thumbnails) and `xdg-user-dirs` (Desktop, Documents, Downloads… with their own icons), plus new keys in the `Super+F1` cheatsheet.
* **abyss-dwm 6.8_2:** `Super+B` (Cmd+B on a Mac) opens the browser through the Abyss menu. If no browser is installed, it now shows a notification telling you how to install one, instead of silently doing nothing (the ISO ships without a browser).
* Abyss menu, future ISOs: the "No web browser installed" notification now suggests `sudo xbps-install firefox`.

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
