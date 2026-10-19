/* user and group to drop privileges to */
static const char *user  = "nobody";
static const char *group = "nobody";

static const char *colorname[NUMCOLS] = {
	[INIT]   = "#1e1e2e",   /* after initialization */
	[INPUT]  = "#89b4fa",   /* during input */
	[FAILED] = "#f38ba8",   /* wrong password */
};

/* treat a cleared input like a wrong password (color) */
static const int failonclear = 1;
