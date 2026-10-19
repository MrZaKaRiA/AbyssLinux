/* See LICENSE file for copyright and license details. */
static int topbar = 1;                      /* -b  option; if 0, dmenu appears at bottom     */
static int centered = 0;                    /* -c  option; centers dmenu on screen           */
static int min_width = 600;                 /* minimum width when centered                   */
static unsigned int border_width = 0;       /* -bw option; border width around dmenu window  */
static unsigned int line_height = 28;       /* -h  option; minimum height of each bar/line   */
/* -fn option overrides fonts[0]; default X11 font or font set */
static const char *fonts[] = {
	"JetBrainsMono Nerd Font:size=10:antialias=true:autohint=true",
	"Symbols Nerd Font Mono:size=10:antialias=true:autohint=true",
	"monospace:size=10"
};
static const char *prompt      = NULL;      /* -p  option; prompt to the left of input field */
static const char *colors[SchemeLast][2] = {
	/*               fg         bg       */
	[SchemeNorm] = { "#f3e8ff", "#0d0b18" },
	[SchemeSel]  = { "#090514", "#a855f7" },
	[SchemeOut]  = { "#090514", "#38bdf8" },
};
/* -l option; if nonzero, dmenu uses vertical list with given number of lines */
static unsigned int lines      = 0;

/*
 * Characters not considered part of a word while deleting words
 * for example: " /?\"&[]"
 */
static const char worddelimiters[] = " ";
