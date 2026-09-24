# GFYMS Center

GFYMS Center is the native desktop control plane for the Surface Pro 7.

## Updates

The Center reads the repository GitHub Releases API, displays release notes, and keeps the complete release list visible so a user can choose an older release when a newer patch is troublesome.

The selected GFYMS Arch package is downloaded and SHA-256 checked against the release SHA256SUMS asset when present. A privileged helper then installs the package with pacman.

The update path is intentionally limited to GFYMS-owned packages. It does not silently replace the Arch base system.

## Rollback

Before an update, the helper saves the current cached GFYMS package under /var/lib/gfyms/rollback when a matching cached package exists.

The Undo button restores the most recent saved GFYMS package. This is package rollback, not a full filesystem snapshot.

## Feedback

The Center copies gfyms doctor output and opens GitHub Discussions so a user can attach a reproducible hardware report to a regression or feature request.

## Surface Pen

The Center mirrors the categories Microsoft exposes through the Surface app: pressure response, writing hand, top-button behavior, side-button behavior, and pen status.

The Microsoft Surface application itself is not bundled or executed on Linux.

## 24px design system

GFYMS Center uses a 24px radius across cards, tabs, buttons, sliders, inputs and panels.

KDE Plasma has separate Plasma Style and KWin decoration extension points. GFYMS will carry the 24px visual language into those surfaces, but arbitrary third-party applications cannot be forcibly restyled by one distribution setting.
