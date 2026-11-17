# Getting started

Download the latest image and its `SHA256SUMS` file from [Releases](https://github.com/MrZaKaRiA/AbyssLinux/releases/latest). Choose **aarch64** for Apple Silicon virtual machines or **x86_64** for most Intel and AMD PCs. Check the release notes for firmware requirements and known issues.

Verify downloads in the directory containing the ISO and checksum file:

```sh
sha256sum -c SHA256SUMS       # Linux
shasum -a 256 -c SHA256SUMS   # macOS
```

Boot the image in a virtual machine or from installation media. The live user and root password are `voidlinux`. Open **Menu → Install Abyss Linux**, configure the hostname and accounts, and follow the installer. Automatic partitioning changes the selected disk: back up important files and confirm the target first. Reboot and remove the installation media when finished.

For detailed installation information and current requirements, see the [README](https://github.com/MrZaKaRiA/AbyssLinux#install).
