# Contributing to Abyss Linux

Thanks for helping. Abyss is small on purpose, and good contributions keep it that way: simple, readable, and in the spirit of Void and suckless.

## Where things go

| Change | Repository |
|---|---|
| Desktop scripts, configs, installer, build scripts, docs | this repo ([AbyssLinux](https://github.com/MrZaKaRiA/AbyssLinux)) |
| dwm / st / dmenu / slock / tabbed / wmname patches, new suckless releases, new Abyss packages | [AbyssLinuxPMR](https://github.com/MrZaKaRiA/AbyssLinuxPMR) |

The `dwm/`, `st/`, … trees here are the source exactly as shipped. If you change one, also update the matching `patches/10-abyss.patch` in the PMR, or the ISO won't pick the change up.

## Workflow

1. Fork, then branch from `main`.
2. Make the change. Keep shell scripts POSIX `sh` where they already are, and test them with `sh -n` (or `bash -n`).
3. Build and boot an ISO (see the README, "Building the ISO from source"), at least for the architecture you changed. A QEMU VM is enough:
   ```sh
   qemu-system-aarch64 -M virt,accel=hvf -cpu host -smp 4 -m 4G \
     -drive if=pflash,format=raw,readonly=on,file=/opt/homebrew/share/qemu/edk2-aarch64-code.fd \
     -device qemu-xhci -device usb-kbd -device usb-tablet \
     -drive file=void-suckless-dev-aarch64.iso,if=none,id=cd,format=raw,readonly=on -device usb-storage,drive=cd \
     -device virtio-gpu-pci -netdev user,id=n0 -device virtio-net-pci,netdev=n0
   ```
4. Open a pull request. Describe what you changed and how you tested it, and include a screenshot for anything visual.

## Style

* Colours: background `#0d0b18`, text `#f3e8ff`, dim `#a78bfa`, accent `#a855f7`, on-accent `#090514`.
* Fonts in **points** (`size=`), never `pixelsize=`, so they follow `Xft.dpi`.
* `sxhkd` binds only `Super+Alt+<letter>` and media keys. `dwm` owns `Super+<key>`.
* Every file added to `custom-overlay/` gets a row in `docs/abyss-overlay.md`. If it needs a special mode, set it in `builder/abyss-postsetup.sh`.

## Reporting bugs

Open an issue with the ISO version (`cat /etc/os-release`), the architecture, the machine or VM (Lumen, UTM, QEMU, VirtualBox…), what you expected, and what happened. Logs that help:

* `~/.local/share/xorg/startx.log` (desktop start)
* `/run/abyss-boot.log` (silent boot)
* `/dev/tty8` during install (the installer log)
