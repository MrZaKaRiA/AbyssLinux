# ==============================================================================
# /etc/profile.d/99-void-dev-cli.sh
# Interactive Developer Shell Environment, Safe Natural XBPS Wrappers,
# Interactive Fuzzy Package Manager (pkg-ui), Git-Aware 2-Line PS1 & Aliases
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
    export EDITOR=vim VISUAL=vim
fi

# 2. Natural XBPS Package Management Functions
update() {
    sudo xbps-install -S
}

upgrade() {
    sudo xbps-install -Su "$@"
}

search() {
    xbps-query -Rs "$@"
}

remove() {
    sudo xbps-remove -R "$@"
}

cleanup() {
    sudo xbps-remove -Oo
}

# Safe `install` wrapper:
# Delegates to GNU coreutils `/usr/bin/install` (`command install`) whenever
# any option flag starting with `-` is passed (e.g., `-m`, `-d`, `-D`, `-c`, `-o`, `-g`)
# or when more than 1 path-like argument containing `/` is passed.
# Otherwise installs packages via `sudo xbps-install -S "$@"`.
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

    sudo xbps-install -S "$@"
}

# 3. Interactive Fuzzy Package Manager (pkg-ui)
pkg-ui() {
    if ! command -v fzf >/dev/null 2>&1; then
        echo "fzf is required for pkg-ui." >&2
        return 1
    fi

    local selected
    selected=$(
        xbps-query -Rs "" |
        fzf --multi \
            --ansi \
            --prompt="📦 Void Packages > " \
            --header="TAB: multi-select | ENTER: install | ESC: cancel" \
            --preview='pkg=$(echo {2} | sed "s/-[^-]*$//"); xbps-query -R "$pkg" 2>/dev/null || xbps-query -R {2}' \
            --preview-window="right:60%:wrap" |
        awk '{print $2}' |
        sed 's/-[^-]*$//'
    )

    if [ -n "$selected" ]; then
        # shellcheck disable=SC2086
        sudo xbps-install -S $selected
    fi
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
