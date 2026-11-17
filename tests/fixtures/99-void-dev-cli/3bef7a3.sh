# ==============================================================================
# /etc/profile.d/99-void-dev-cli.sh
# Lightweight interactive shell helpers and Void package shortcuts
# ==============================================================================

# 1. Interactive shell guard — never affect non-interactive scripts or Makefiles
case $- in
    *i*) ;;
    *) return ;;
esac

export PATH="/usr/local/bin:${HOME}/.local/bin:${PATH}"
if command -v code >/dev/null 2>&1; then
    export EDITOR="code --wait" VISUAL="code --wait"
else
    export EDITOR=vi VISUAL=vi
fi

# Run a command as root: directly when the shell already is root (doas only
# knows the wheel rules, and root needs no privilege tool), otherwise through
# doas, or sudo when doas is absent.
abyss_priv() {
    if [ "$(id -u)" -eq 0 ]; then "$@"
    elif command -v doas >/dev/null 2>&1; then doas "$@"
    else sudo "$@"; fi
}

# 2. Natural XBPS Package Management Functions
# Wait politely while another xbps command holds the package database.
__abyss_xbps_wait() {
    __abyss_xbps_busy || return 0
    echo "Another install or update is running; this one will start when it finishes. (Ctrl+C cancels)" >&2
    while __abyss_xbps_busy; do sleep "${ABYSS_LOCK_POLL:-2}"; done
}
__abyss_xbps_busy() {
    pgrep -x xbps-install >/dev/null 2>&1 || pgrep -x xbps-remove >/dev/null 2>&1
}

# Update the package lists; retry network errors twice before explaining.
update() {
    local try=1 log rc
    log=$(mktemp) || return 1
    __abyss_xbps_wait
    while :; do
        # Stream the output (xbps may ask to import a repository key).
        { abyss_priv xbps-install -S; echo $? >"$log.rc"; } 2>&1 | tee "$log"
        rc=$(cat "$log.rc" 2>/dev/null || echo 1); rm -f "$log.rc"
        if [ "$rc" -eq 0 ] && ! grep -q ERROR "$log"; then rm -f "$log"; return 0; fi
        grep -qiE 'authentication failed|not permitted' "$log" && break
        [ "$try" -lt 3 ] || break
        echo "A package server could not be reached; trying again in ${ABYSS_RETRY_PAUSE:-5}s..." >&2
        sleep "${ABYSS_RETRY_PAUSE:-5}"; try=$((try + 1))
    done
    if grep -qiE 'authentication failed|not permitted' "$log"; then
        echo "Updating the package lists needs your password." >&2
    elif grep -qiE 'resolv|name or service' "$log"; then
        echo "The package servers could not be found (DNS). Check your network connection, then run: update" >&2
    else
        echo "The package lists could not be updated. Check your network connection, then run: update" >&2
    fi
    rm -f "$log"
    return 1
}

upgrade() {
    update || echo "Upgrading with the package lists already on this computer." >&2
    __abyss_xbps_wait
    abyss_priv xbps-install -u "$@"
}

search() {
    xbps-query -Rs "$@"
}

remove() {
    abyss_priv xbps-remove -R "$@"
}

cleanup() {
    abyss_priv xbps-remove -Oo
}

# Safe `install` wrapper:
# Delegates to GNU coreutils `/usr/bin/install` (`command install`) whenever
# any option flag starting with `-` is passed (e.g., `-m`, `-d`, `-D`, `-c`, `-o`, `-g`)
# or when more than 1 path-like argument containing `/` is passed.
# Otherwise installs packages via XBPS with doas (or sudo if installed).
install() {
    if [ "$#" -eq 0 ]; then
        command install
        return $?
    fi

    local arg
    local slash_count=0
    for arg in "$@"; do
        case "$arg" in
            -*)
                command install "$@"
                return $?
                ;;
            */*)
                slash_count=$(( slash_count + 1 ))
                ;;
        esac
    done

    if [ "$slash_count" -gt 1 ]; then
        command install "$@"
        return $?
    fi

    update || echo "Continuing with the package lists already on this computer." >&2
    __abyss_xbps_wait
    abyss_priv xbps-install "$@"
}

# 3. Searchable dmenu package browser
pkg-ui() {
    command -v abyss-software >/dev/null 2>&1 && abyss-software --search || {
        echo "abyss-software is not installed." >&2
        return 1
    }
}

# 4. Abyss Linux Cosmic Neon PS1 Prompt
__abyss_git_branch() {
    command -v git >/dev/null 2>&1 || return
    local branch dirty=""
    branch=$(git symbolic-ref --short HEAD 2>/dev/null || git rev-parse --short HEAD 2>/dev/null) || return
    if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
        dirty="*"
    fi
    printf " \001\033[1;38;5;51m\002(%s%s)\001\033[0m\002" "$branch" "$dirty"
}

__abyss_prompt_cmd() {
    local u_col="197"
    if [ "$(id -u)" -eq 0 ]; then
        u_col="196"
    fi
    PS1="${debian_chroot:+($debian_chroot)}\[\e[1;38;5;${u_col}m\]\u\[\e[0m\]\[\e[38;5;250m\] at \[\e[1;38;5;141m\]\h\[\e[0m\] \[\e[38;5;244m\]in \[\e[1;38;5;191m\]\W\[\e[0m\]\$(__abyss_git_branch) \[\e[1;38;5;${u_col}m\]\$\[\e[0m\] "
}

if [ -n "${BASH_VERSION:-}" ]; then
    PROMPT_COMMAND=__abyss_prompt_cmd
fi

# 5. Modern CLI Tool Aliases
if command -v eza >/dev/null 2>&1; then
    alias ls='eza --icons --group-directories-first'
    alias ll='eza -la --icons --group-directories-first --git'
    alias lt='eza --tree --level=2 --icons --group-directories-first'
fi

if command -v bat >/dev/null 2>&1; then
    alias cat='bat --style=plain --paging=never'
fi

if command -v btop >/dev/null 2>&1; then
    alias top='btop'
fi
