# ~/.bashrc - Void Linux Suckless Developer Workstation

# If not running interactively, don't do anything
[[ $- != *i* ]] && return

HISTCONTROL=ignoreboth:erasedups
HISTSIZE=10000
HISTFILESIZE=20000
shopt -s histappend
shopt -s checkwinsize

# Source global definitions and Void developer CLI profile
if [ -f /etc/bashrc ]; then
    . /etc/bashrc
fi

if [ -f /etc/profile.d/99-void-dev-cli.sh ]; then
    . /etc/profile.d/99-void-dev-cli.sh
fi

if [ -f /usr/share/bash-completion/bash_completion ]; then
    . /usr/share/bash-completion/bash_completion
fi

# Fallback PS1 if profile was not loaded
if [ -z "${PROMPT_COMMAND:-}" ]; then
    PS1='${debian_chroot:+($debian_chroot)}\[\e[1;38;5;197m\]\u\[\e[0m\]\[\e[38;5;250m\] at \[\e[1;38;5;141m\]\h\[\e[0m\] \[\e[38;5;244m\]in \[\e[1;38;5;191m\]\W\[\e[0m\] \[\e[1;38;5;197m\]\$\[\e[0m\] '
fi

# ---- Abyss Linux shell layer --------------------------------------------------
# Vi editing mode (Esc = normal mode; Caps Lock is Escape under X)
set -o vi
bind -m vi-insert '"\C-l": clear-screen'
bind -m vi-insert '"\C-a": beginning-of-line'
bind -m vi-insert '"\C-e": end-of-line'

# XBPS shortcuts, privileged through doas (falls back to sudo if doas is absent)
if command -v doas >/dev/null 2>&1 && [ -e /etc/doas.conf ]; then
    __abyss_priv=doas
else
    __abyss_priv=sudo
fi
alias u="$__abyss_priv xbps-install -Su"     # update the whole system
alias i="$__abyss_priv xbps-install -S"      # install: i <pkg>...
alias q='xbps-query -Rs'                     # query/search: q <term>
alias r="$__abyss_priv xbps-remove -R"       # remove with orphaned deps: r <pkg>...

# Power: go through abyss-power, which falls back to a clean manual shutdown
# if runit's normal path fails (see `abyss-power diagnose`)
alias poweroff='abyss-power poweroff'
alias reboot='abyss-power reboot'
