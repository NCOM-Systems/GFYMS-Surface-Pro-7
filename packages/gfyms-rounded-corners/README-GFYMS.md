# GFYMS 24px KDE shell integration

This package builds the pinned upstream KDE-Rounded-Corners KWin effect and supplies GFYMS defaults for a 24px corner radius.

Upstream: https://github.com/matinlotfali/KDE-Rounded-Corners
Commit: c1178d94ff2ec0db8d4d9a9782a3eb06aec13ce6
License: GPL-3.0-only

GFYMS does not claim authorship of the upstream effect. The GFYMS package only supplies the Arch packaging and default configuration.

The system default is enabled for `shapecorners` and sets both active and inactive corner radii to 24px. A user's `~/.config/kwinrc` can override the system default.