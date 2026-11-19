# Updates and troubleshooting

Update installed XBPS packages from the enabled Void and Abyss repositories:

```sh
doas xbps-install -Su
```

No packages offered can simply mean the enabled repositories have no newer versions. Check installed package versions with `xbps-query -p pkgver abyss-desktop` and configured repositories with `xbps-query -L`. The [Abyss PMR](https://github.com/MrZaKaRiA/AbyssLinuxPMR) supplies Abyss-specific packages; software installed directly from a vendor may update separately.

For a launcher error, update packages first and log out and back in. If it persists, include the exact error, package version and steps to reproduce in an [issue](https://github.com/MrZaKaRiA/AbyssLinux/issues). Avoid posting passwords or private files.

If a shortcut fails, check the active shortcut settings, confirm the target application is installed and try launching it from a terminal to see any error. For display problems, choose a mode reported by the connected display or VM and check the virtual display settings on the host.

## Disk space

After every successful `upgrade`, `install`, **Software › Update system** or install from **Install software**, Abyss removes the cached packages that were replaced by newer versions (`xbps-remove -O`) and prints how much that freed. The current versions stay in `/var/cache/xbps` so they can be reinstalled offline. Packages nothing needs any more (orphans) are only named; remove them with `cleanup` when you have checked the list.

**Menu › System › Free up disk space** shows the package cache, old kernels (`vkpurge`) and unneeded packages, asks before removing each, and then runs TRIM. It asks for your password once.

The `abyss-fstrim` service runs `fstrim -a` once a week (10 minutes after boot at the earliest; a week spent switched off or asleep counts), so SSDs keep their speed and a virtual machine's disk image shrinks after files are deleted. Its log is `/var/log/abyss-fstrim.log`; turn it off with `doas rm /var/service/abyss-fstrim`. A virtual disk only takes TRIM when the hypervisor passes it through (QEMU: `discard=unmap` on the drive).
