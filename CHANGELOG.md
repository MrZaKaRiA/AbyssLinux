# Changelog

## Next ISO (unreleased)

* **Boot to desktop in one picture:** Plymouth "Abyss" splash from the initramfs, then a LightDM login screen on the same artwork with your user preselected and the password box at the bottom centre (`quiet splash`). The live ISO logs in automatically; the installer turns that off for installed systems. No text login on tty1 any more (tty2-6 stay available).
* **Shutdown fixed:** `poweroff`/`reboot` failed on some installs with `init: fatal: unable to create /etc/runit/stopit`. A boot-time repair (`/etc/runit/core-services/11-abyss-runit-ctl.sh`) relinks runit's control files, and the new `abyss-power` helper falls back to a clean manual shutdown if runit's path still fails. `abyss-power diagnose` prints the details.
* **Abyss menu, reorganised:** a header with user, host and uptime, then Terminal, Files and Web browser, then an **Applications** submenu built from your installed apps. Apps are grouped by category, with their real icons and a short description ("Thunar · File Manager"), plus search and run. Settings are grouped into Network, Sound, Display (including text size), Keyboard and Appearance; System has a monitor, disks, services and power diagnostics; Session holds lock, sleep, log out, restart and shut down.
* **rofi app search** now shows icons and what each app is.
* **Status bar:** compact, icon based: network ↓/↑ speed, CPU % with temperature (when the machine has a sensor), RAM, disk, clock.
* **Installer:** Abyss texts and defaults ("Enter the abyss", "Abyss Linux installation menu").
* Shell: `poweroff`/`reboot` aliases go through `abyss-power`; vi mode and the `u`/`i`/`q`/`r` xbps aliases.
* Build: the macOS builder VM moved from `/tmp` to `~/Library/Caches/abyss-builder` (macOS cleans `/tmp`, which broke the builder's network), and a failed x86_64 build no longer deletes the previous ISO.

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
