I got tired of compiling suckless from source, so I built a systemd-free, rolling-release distro where dwm just works: Abyss Linux (Void-based)

I started on the big distros: Ubuntu, Debian. I respect the work behind them, but they never felt like *my* system. A fresh install came with a pile of services and packages I never asked for, and at the center of it all was systemd, which for my taste does far too much for an init system. I wanted the opposite: a minimal system, rolling release, no systemd, with the suckless tools I actually live in (dwm, st, dmenu).

Void Linux got me most of the way there: runit, rolling releases, a fast package manager, and nothing installed that I didn't choose. But the suckless side stayed a headache. The suckless way is to patch config.h and the C source and compile everything yourself. I like that philosophy, but in practice it meant rebuilding dwm by hand, re-applying patches that stopped applying after an update, and keeping my own binaries alive outside the package manager. If it was a chore for me, I'm sure it stops a lot of people who would love this setup.

So I set myself a goal: make minimal + rolling + no systemd + suckless something anyone can install, without compiling anything.

That's Abyss Linux. Some details for the people who like details:

**The suckless tools are real packages.** dwm (systray, status2d, vanitygaps, scratchpad), st, dmenu, slock, tabbed and wmname come as signed abyss-* packages from my own repo (github.com/MrZaKaRiA/AbyssLinuxPMR). The templates keep my changes as patch files against the upstream tarballs, so you can read exactly what I changed. `xbps-install -Su` updates dwm like anything else. If you want to tinker, fork the template and go.

**It's still Void.** Everything else comes from the official Void repos. Abyss is an overlay and a few hooks on top of void-mklive. I don't edit mklive itself, my tweaks (volume label, hostname, hidden GRUB menu) go on a temporary copy at build time, so updating mklive is easy.

**I build it on a Mac.** My daily machine is an Apple Silicon MacBook, so the build script starts a small Void aarch64 VM in QEMU (HVF acceleration) and shares the repo into it over 9p. mklive runs inside that VM for aarch64, then x86_64 through qemu-user/binfmt. One command, two ISOs.

That setup gave me my favorite bug so far. mklive copies the overlay with `cp -p`, so all my files ended up in the ISO owned by uid 501, my macOS user. I only noticed when doas refused to work because doas.conf wasn't owned by root (which is the right behavior). Now a post-setup hook goes through the overlay file list and fixes owner and permissions on exactly those files. If you build images from macOS, check this.

**I test it in my own VM app.** It's called Lumen, a SwiftUI VM manager for Apple Silicon on top of Apple's Virtualization framework. That turned out useful: when Super+key didn't reach dwm, I could check both what the host was sending and what X was getting with xev.

**One menu instead of a row of useless icons.** My first bar had a bunch of icons and none of them did anything. Now there's a compact status area (network speed, CPU and temperature, RAM, disk, clock) and one menu button. Click it or press Super+Escape and you get an xmenu popup: your apps sorted by category with their icons and a one-line description (so "lf" or "Thunar" explain themselves), plus settings, system tools and power. It uses dwm's existing status click handler, so I didn't have to rebuild dwm for it. sxhkd only handles keys dwm doesn't grab, so they don't fight.

**One picture from power on to desktop.** Plymouth shows the Abyss artwork from the initramfs, then LightDM takes over the same frame (`plymouth quit --retain-splash` and X started with `-background none`), so there's no text login flashing in between. The greeter uses the same picture with your user already picked and the password box at the bottom. Getting a clean quiet boot on runit was the fun part: stage 1 prints its "=> ..." lines and has no quiet option, but /etc/runit/1 sources /etc/rc.conf early, so my rc.conf checks `$0` and when it's stage 1 or 3 with `quiet` on the kernel line, sends the output to /run/abyss-boot.log. It also overrides emergency_shell so you still see what went wrong if fsck fails. No runit files patched. I'd really like to hear from Void people if there's a cleaner way to do this.

**Arabic out of the box.** English + Arabic (Western digits), Alt+Shift to switch, Caps Lock as Escape. One thing I learned that other dwm users might hit: dwm looks up keys in the first XKB layout group. If Arabic is group 1, all your Super+letter bindings just stop working, no error. So Latin stays group 1 and switching uses a group lock instead of reordering the layouts.

Small stuff: doas instead of sudo, bash in vi mode, `u` / `i` / `q` / `r` for xbps update / install / search / remove, startx only on tty1, sizes that follow your screen DPI, and Super+F1 for a cheatsheet of the actual keybindings.

What I'm looking for:

- feedback on the rc.conf trick (or a better idea)
- people to try it on real x86_64 hardware, I've mostly tested aarch64 in VMs
- Arabic / RTL users, tell me what breaks in st and dmenu
- which suckless patches you'd want packaged next

Repo: github.com/MrZaKaRiA

It's early and there are rough edges, but it's the system I wanted for myself, and I'd like other people to have it without compiling it. Thanks for reading.
