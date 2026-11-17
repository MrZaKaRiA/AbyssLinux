# Changelog

## v27.3.3 (2026-11-17)

* Displays: outputs without a saved choice now run at the highest refresh rate their resolution offers (opt out with `echo preferred > ~/.config/abyss/refresh-auto`). The largest screen becomes primary. `abyss-display --full-range` fixes washed-out blacks over HDMI on Intel graphics.
* Displays: the resolution is automatic unless you fix one. It follows the display's preferred mode (the native mode of a monitor, the window size in a virtual machine), also while logged in: plugging in a monitor, or resizing a VM window or making it full screen, is picked up within a few seconds. Saving a layout or choosing a refresh rate no longer records a resolution; only a size picked in **Resolution and refresh rate** is fixed, and the top entry of that list, **Automatic resolution (follow the display / VM window)**, or **Settings › Display › Resolution: …**, which shows whether it is automatic or fixed, undoes it at once. Positions and switched-off outputs of a saved layout are kept. A resolution saved for a virtual display by 27.3.2 or an earlier 27.3.3 package is ignored, so a virtual machine follows its window again without any clean-up; on real hardware a previously saved resolution stays until you choose the automatic entry.
* Fixed: `update`, `upgrade`, `install`, `remove`, `cleanup` and the `u`/`i`/`r` aliases failed in a root shell because they always went through doas, which had no rule for root. Root now runs them directly, and `/etc/doas.conf` gains `permit nopass root`; existing installs get that rule added once by the abyss-desktop update.

* Scale the mouse pointer with the desktop text size, including at login, while respecting a custom cursor theme.
* Size the mouse pointer for the screen as well as the text size, so a high-resolution display no longer gets a tiny pointer, without growing oversized: 24 px on a 1080p screen, 32 px at 1440p, 48 px on 4K or at 200% text. **Settings › Display › Pointer size** sets a fixed size; the pointer is re-fitted after every resolution change.
* Add **Settings › Display › Refresh rate (keeps resolution)**: pick a refresh rate on its own. The resolution stays automatic, the rate is remembered per display and re-applied after display detection, and a 20-second keep/revert prompt protects against a rate the panel cannot show.
* "Detect displays again" now keeps a saved refresh rate instead of resetting it.
* Bring back the Abyss popup menu: since 27.2 the image had no `xmenu`, so **Menu** (or `Super+Esc`) opened a long list instead. `xmenu` and `xdotool` are installed again (dependencies of `abyss-desktop`, so a system update restores the popup). It opens under the Menu button with submenus and icons: Terminal, Files and Web browser, then Applications, Media (images, screenshots, screen recording, play a copied URL), Software, Settings and System, and **Session** as the last row for lock, suspend, restart and shut down. **Search menu…** opens the same entries as a list where typing finds any of them.
* Installer: check free space before copying, stop with a clear message when the copy or the initramfs build fails, and show the last log lines when GRUB cannot be installed (a full host disk under a virtual machine is the usual cause). The copy, GRUB and initramfs steps are logged to `/tmp/abyss-install.log`.
* Boot: GRUB waits 1 second instead of 2, and the `virtio_rng` driver is in the initramfs so virtual machines no longer stall about 4 seconds waiting for entropy.
* ISO audit: fail the build when `/var/lib/lightdm`, `/etc/doas.conf` or the sudo power rule has the wrong owner or mode.
* Bring back the Abyss wallpaper: since 27.2 the image had no program to draw it, so the desktop was plain black. `feh` is installed again (a dependency of `abyss-desktop`, so a system update restores the wallpaper at the next login) and one helper, `abyss-wallpaper`, draws it once per login. **Settings › Display › Wallpaper: Abyss / black (OLED)** switches it; `~/.config/abyss/wallpaper` holds `none` or the path of your own image.

* Fix the slock privilege-drop group on Void and coordinate suspend with its lock readiness.
* Start the desktop D-Bus session before audio services and coordinate xss-lock sleep requests with slock after the screen is locked.
* Add bounded st scrollback, reduce battery polling, and offer optional terminal, TeX, and media bundles.
* Add Vim TeX build and SyncTeX navigation, clipboard media playback, and an X11 screen recorder.

* Repair the malformed Rofi configuration shipped in older Abyss images while preserving user edits and backing up the original file.
* Update the download links, release counter, and checksums in the README for 27.3.
* Wallpaper manager: **Settings › Display › Wallpaper…** (`abyss-wallpapers`) lists the system wallpapers and your own, adds an image (copied to `~/.local/share/backgrounds`), previews them in nsxiv, removes your images and sets how the image is placed (fill, fit, centre, tile; kept in `~/.config/abyss/wallpaper-mode`). `~/.config/abyss/wallpaper` keeps its one-line format; `abyss-wallpapers list|set|add|remove|mode` do the same from a script.

## v27.3 (2026-11-10)

* Improved the Thunar sidebar and theme, with a one-time HiDPI width repair and folder shortcuts when no bookmarks exist.
* Made GTK 4 and libadwaita file dialogs use Abyss’s dark appearance by default.

## v27.2 (2026-11-10)

* Reduced the default image to Void's desktop foundation and the Abyss suckless packages. Browsers, editors, audio, Bluetooth, virtualization, containers, media, and creative apps install only when selected.
* Added a dmenu software window with Void package search and official current-version installers for VS Code, ArtCraft Launcher, Ollama, Claude Code, OpenCode, Cursor, and vendor download pages.
* Added first-run keyboard, optional repository, and runit service setup.
* Added network, battery, and optional PipeWire volume indicators; monitor profiles, refresh-rate selection, and optional OLED screen blanking.
* Fixed the stray Rofi config terminator and widened/centered the LightDM login fields.
* Removed default startup of SSH, Docker, and Ollama services.
* Added editable dwm shortcuts, conflict detection, screenshot actions, and the nsxiv image viewer with the `img` command.
* Fixed VS Code and other oversized floating dialogs, narrow GTK file chooser sidebars, and discovery of user-installed VS Code.
* Added automatic text sizing and a timed rollback for text-size changes; resolved a package conflict with Void’s login greeter.

## v27.1 (2026-10-21)

ISOs: `abyss-linux-27.1-aarch64.iso`, `abyss-linux-27.1-x86_64.iso`

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
