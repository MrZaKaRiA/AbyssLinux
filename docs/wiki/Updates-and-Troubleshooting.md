# Updates and troubleshooting

Update installed XBPS packages from the enabled Void and Abyss repositories:

```sh
doas xbps-install -Su
```

No packages offered can simply mean the enabled repositories have no newer versions. Check installed package versions with `xbps-query -p pkgver abyss-desktop` and configured repositories with `xbps-query -L`. The [Abyss PMR](https://github.com/MrZaKaRiA/AbyssLinuxPMR) supplies Abyss-specific packages; software installed directly from a vendor may update separately.

For a launcher error, update packages first and log out and back in. If it persists, include the exact error, package version and steps to reproduce in an [issue](https://github.com/MrZaKaRiA/AbyssLinux/issues). Avoid posting passwords or private files.

If a shortcut fails, check the active shortcut settings, confirm the target application is installed and try launching it from a terminal to see any error. For display problems, choose a mode reported by the connected display or VM and check the virtual display settings on the host.
