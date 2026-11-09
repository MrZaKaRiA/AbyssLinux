# Abyss overlay additions

The ISO installs the Void base and Xorg runtime, the LightDM greeter, networking,
installer dependencies, and Abyss's upstream-based suckless packages. General
applications are installed on demand through XBPS or official vendor downloads.

## Main desktop scripts

| Path | Purpose |
|---|---|
| `/usr/local/bin/abyss-control-center` | dmenu-first menu for apps, package search, display settings, updates, services, and power actions. |
| `/usr/local/bin/abyss-software` | Search Void packages and install curated packages or current official vendor releases. |
| `/usr/local/bin/abyss-setup` | First-run keyboard setup, optional repository setup, optional runit services, and display settings. |
| `/usr/local/bin/abyss-display` | XRandR display layout, resolution, refresh rate, and saved monitor profiles. |
| `/usr/local/bin/dwm-statusbar` | Network type and transfer rate, battery and volume when available, CPU, RAM, time, and menu. |
| `/usr/local/bin/abyss-keyboard` | Per-user XKB layout, Caps-to-Escape, VM Super-key helper, and keyboard diagnostics. |
| `/usr/local/bin/abyss-installer` | Opens Void's installer in the Abyss `st` terminal. |
| `/usr/local/bin/abyss-power` | Runit-aware power actions and diagnostics. |
| `/usr/local/bin/abyss-priv` | Selects doas, or sudo if installed, for privileged commands. |
| `/usr/local/bin/abyss-apps` | Builds the optional installed-app menu from desktop files. |
| `/usr/local/bin/abyss-shortcuts` | Minimal dwm shortcut reference (`Super+F1`). |

## User session and login

* `/etc/lightdm/lightdm.conf.d/50-abyss.conf` selects the Abyss session.
* `/etc/lightdm/lightdm-gtk-greeter.conf` centers the login panel and uses a
  larger font; `/var/lib/lightdm/.config/gtk-3.0/gtk.css` gives its fields more
  width and height.
* `/usr/local/bin/abyss-display-setup` applies the greeter's HiDPI setting.
* `/usr/local/bin/abyss-session` starts the user's `~/.xinitrc`.
* `custom-overlay/etc/skel/.xinitrc` applies Xft DPI, restores display profiles,
  starts dwm and optional user-installed PipeWire components, and offers the
  first-run setup window.
* `/etc/skel/.config/abyss/keyboard.conf` supplies the initial keyboard layout.
* `/etc/doas.conf` enables wheel administration; `/etc/sudoers.d/abyss-power`
  allows the narrowly scoped power helper.

## Build hooks

* `builder/abyss-mklive-tweaks.sh` patches a working copy of void-mklive to set
  the hidden GRUB menu, ISO label, live hostname, and PMR signing key.
* `builder/abyss-postsetup.sh` normalizes overlay ownership and file modes,
  writes the build version, and reports missing core binaries.

The package list is deliberately small. Browsers, editors, audio, Bluetooth,
virtualization, containers, media, and creative tools are offered after boot.
The suckless packages come from the signed Abyss PMR, built from upstream
release sources with documented patches.
