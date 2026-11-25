# vim: set ts=4 sw=4 et:
# Abyss Linux: make sure poweroff/reboot can reach runit.
# runit-init writes /etc/runit/stopit and /etc/runit/reboot, which must be
# symlinks to the files 10-runit-control.sh just created in /run/runit.
# If an install left them broken, "poweroff" fails with
# "init: fatal: unable to create /etc/runit/stopit". Fix them on every boot.

[ -n "$IS_CONTAINER" ] && return 0

for _f in stopit reboot; do
    if [ "$(readlink /etc/runit/$_f 2>/dev/null)" != "/run/runit/$_f" ]; then
        msg_warn "Repairing /etc/runit/$_f"
        rm -f /etc/runit/$_f && ln -s /run/runit/$_f /etc/runit/$_f
    fi
done
unset _f
