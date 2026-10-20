# Abyss overlay additions

Everything below lives in `custom-overlay/` (copied into the ISO by `mklive -I`)
or `builder/` (build-time hooks). The suckless tools are **not** in the overlay: the
ISO installs `abyss-dwm`, `abyss-st`, `abyss-dmenu`, `abyss-slock`, `abyss-tabbed` and
`abyss-wmname` and the GTK/icon theme `abyss-theme` from the signed [Abyss PMR](https://github.com/MrZaKaRiA/AbyssLinuxPMR)
(see "Suckless packages" below).
The builder deletes the old ISO before copying the new one, so a VM that has it open keeps the old file.

## Files

| Target path in the ISO | Mode | Purpose |
|---|---|---|
| `/usr/local/bin/abyss-control-center` | 0755 | The single top-right menu (xmenu, nested submenus; dmenu fallback). dwm already runs it on status-bar click and Super+Escape. Sizes follow Xft.dpi. On the live ISO the first entry is *Install Abyss Linux*. `--check` lists missing deps. |
| `/usr/local/bin/abyss-installer` | 0755 | Opens void-installer as root in its own st window with a large font (`size=14`, scaled by Xft.dpi) and the purple accent. |
| `/usr/bin/void-installer` | 0755 | Upstream installer; title is "Abyss Linux installer (<build date>)", exports `DIALOGRC=/etc/dialogrc`, resets the installed tty1 to a normal login prompt (the live autologin user `anon` is deleted), removes xmirror before dialog. |
| `/etc/dialogrc` | 0644 | Dark, high-contrast dialog theme: light text on black, purple highlight, no shadow. |
| `/usr/local/bin/dwm-statusbar` | 0755 | Minimal status text: CPU, RAM, clock, `offline` only when there is no network, and a purple ` Menu ` button. |
| `/usr/local/bin/abyss-keyboard` | 0755 | setxkbmap us,ara(digits), Alt+Shift toggle, Caps=Esc, optional Super-on-Left-Alt, `--status`, `--test`. |
| `/usr/local/bin/abyss-shortcuts` | 0755 | Cheatsheet, now matching the real `dwm/config.h` bindings. |
| `/etc/X11/xorg.conf.d/00-keyboard.conf` | 0644 | Same layout/options at server level (covers hotplugged keyboards). |
| `/etc/rc.conf` | 0644 | Stock Void rc.conf + silent-boot block: with `quiet`, runit stage 1/3 output goes to `/run/abyss-boot.log`; console is restored if boot drops to the emergency shell. |
| `/etc/sv/agetty-tty1/conf` | 0644 | Silent autologin (`--skip-login --nonewline --noissue -a anon`). |
| `/etc/default/grub` | 0644 | Installed systems: hidden menu, `quiet loglevel=3`. |
| `/etc/doas.conf` | **0400 root:root** | `permit persist keepenv :wheel` + passwordless reboot/poweroff/zzz/ZZZ. |
| `/etc/skel/.bash_profile` | 0644 | startx on tty1 only (no DISPLAY/WAYLAND/SSH, no running Xorg); X output → `~/.local/share/xorg/startx.log`. |
| `/etc/skel/.bashrc` | 0644 | Appended: `set -o vi`, aliases `u i q r` (doas, falls back to sudo). |
| `/etc/skel/.xinitrc` | 0755 | Adds xrdb, HiDPI `Xft.dpi` (192 from 1700 px screen height, 144 from 1300; override in `~/.config/abyss/dpi`), abyss-keyboard, `xdg-user-dirs-update` (Desktop, Documents, Downloads… with their own folder icons), sxhkd, welcome notification; nm-applet now opt-in from the menu. |
| `/etc/skel/.Xresources` | 0644 | xmenu theme (Abyss purple). |
| `/etc/skel/.config/sxhkd/sxhkdrc` | 0644 | Super+Alt+letter and media keys only — never keys dwm grabs. r/w rofi apps/windows, f lf, v vim, c/h dunst close/history. |
| `/usr/local/bin/abyss-launcher` | 0755 | rofi launcher (`drun`, `run`, `window`) with `-dpi` from Xft.dpi; dmenu fallback. Menu > Apps / Run program. |
| `/etc/skel/.config/rofi/config.rasi` | 0644 | rofi config + Abyss theme (dark, purple selection, em-based sizes). |
| `/etc/skel/.config/dunst/dunstrc` | 0644 | Notifications: dark with purple frame, top-right under the bar, `scale = 0` (follows Xft.dpi). |
| `/etc/skel/.config/lf/lfrc`, `lf/preview` | 0644 / 0755 | lf file manager; Enter opens text in $EDITOR, video/audio in mpv, images in feh; previews via bat/chafa/file. |
| `/etc/skel/.config/mpv/mpv.conf` | 0644 | mpv defaults (keep-open, resume position, `vo=gpu,x11` for VMs without 3D). |
| `/etc/skel/.vimrc` | 0644 | vim defaults (habamax on the terminal background, persistent undo, mouse). |
| `/etc/profile.d/99-void-dev-cli.sh` | 0644 | `EDITOR`/`VISUAL` = VS Code when installed, otherwise vim. |
| `/etc/skel/.config/abyss/keyboard.conf` | 0644 | Per-user keyboard settings read by abyss-keyboard. |
| `/etc/skel/.hushlogin` | 0644 | No motd / last-login text on autologin. |

## Build hooks

* `builder/abyss-mklive-tweaks.sh <mklive-copy>` — run on a *copy* of void-mklive:
  hidden live GRUB menu (2 s, hold Esc/Shift to show), volume label `ABYSS_LIVE`,
  live hostname `abyss-live`.
* `builder/abyss-postsetup.sh <rootfs>` — passed as `mklive -x`. Makes every
  overlay path `root:root` (mklive's `cp -p` otherwise keeps the macOS uid 501),
  sets the modes above, deletes `.DS_Store`, fills the installer title version
  (`ABYSS_VERSION`, default: build date), warns if menu/keyboard packages are missing.
* Both build scripts now pass `-C "quiet loglevel=3 rd.udev.log_level=3 udev.log_level=3"`,
  `SPLASH_IMAGE=…/abyss-splash.png` (GRUB background) and add the packages
  `xmenu xdotool sxhkd setxkbmap xrdb xmodmap xev opendoas mpv vim lf rofi dunst file chafa`.

## Suckless packages (Abyss PMR)

`dwm/`, `st/`, `dmenu/`, `slock/`, `tabbed/` and `wmname/` in this repository are the
patched sources as shipped. The ISO does not compile them; it installs the matching
packages from `https://mrzakaria.github.io/AbyssLinuxPMR/current` (`mklive -r`), whose
templates carry the same changes as patch files against the release tarballs.

* Repository config: `/etc/xbps.d/20-abyss-pmr.conf`
* Signing key: `keys/abyss-pmr.plist`, installed by `builder/abyss-mklive-tweaks.sh` as
  `/var/db/xbps/keys/c6:f0:d1:05:cb:f1:89:83:58:c2:e2:e4:4c:c9:09:9a.plist`
* To change a suckless tool: edit the tree here to try it, then update the patch in the
  PMR template and bump `revision`. Installed systems get it with `xbps-install -Su`.

## Rebuild

The builder VM skips an ISO that already exists, so force it:

```bash
FORCE_REBUILD=1 ./build-distro.sh
```

## Verbose boot when debugging

Press Esc at boot, `e` on the entry, delete `quiet`, Ctrl+X. The quiet-boot
log of the last boot is always in `/run/abyss-boot.log`.
