#!/bin/sh
# ==============================================================================
# ~/.dwm/autostart.sh - Abyss Linux dwm Autostart Hook
# ==============================================================================

# Set cosmic wallpaper
if command -v feh >/dev/null 2>&1 && [ -f /usr/share/backgrounds/abyss/abyss-wallpaper.jpg ]; then
    feh --bg-fill /usr/share/backgrounds/abyss/abyss-wallpaper.jpg &
fi
