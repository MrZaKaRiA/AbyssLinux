# ~/.bash_profile - Abyss Linux

if [ -f "$HOME/.bashrc" ]; then
    . "$HOME/.bashrc"
fi

# The kernel hides the console cursor (vt.global_cursor_default=0) so it never
# blinks over the boot splash; bring it back for text logins on tty2-tty6.
case "$(tty)" in
    /dev/tty[0-9]*) command -v setterm >/dev/null 2>&1 && setterm --cursor on ;;
esac

# Start X (dwm) automatically on tty1 only, and only when:
#   - no X/Wayland display is already set (not inside a GUI terminal or ssh -X)
#   - this is the local console tty1 (not ssh, not tty2-6)
#   - this user has no X server running yet (no second session on top)
# Xorg/xinit chatter goes to a log so the boot stays clean. When X exits you
# land in this shell; type `startx` to go back.
if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ] && [ -z "${SSH_TTY:-}" ] \
    && [ "$(tty)" = "/dev/tty1" ] \
    && ! pgrep -u "$(id -u)" -x Xorg >/dev/null 2>&1 \
    && command -v startx >/dev/null 2>&1; then
    mkdir -p "$HOME/.local/share/xorg"
    startx "$HOME/.xinitrc" -- -keeptty >"$HOME/.local/share/xorg/startx.log" 2>&1
    echo "X session ended (log: ~/.local/share/xorg/startx.log). Type startx to restart."
fi
