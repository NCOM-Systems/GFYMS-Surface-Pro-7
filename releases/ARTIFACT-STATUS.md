# GFYMS release artifact status

| Artifact | Status | Intended delivery |
|---|---|---|
| GFYMS Arch Surface Patcher | Not built | Attached to tagged GitHub release |
| GFYMS Surface Pro 7 ISO | Not built | Attached to tagged GitHub release |
| GFYMS USB Tool | Not built | Attached to tagged GitHub release |

## Why there are no final binaries yet

The project has only just moved from the Surface MSI reverse-engineering phase into OS architecture. The native GFYMS packages, Surface kernel changes, KDE integration, patcher implementation, USB writer implementation, reproducible package repository, and physical Surface Pro 7 qualification still need to be implemented.

We will not label a placeholder Arch image as the official GFYMS Surface OS.

## Target release layout

```text
GFYMS Surface Pro 7 vX.Y.Z
├── GFYMS-Surface-Pro-7-vX.Y.Z-x86_64.iso
├── GFYMS-Surface-Patcher-vX.Y.Z.tar.zst
├── GFYMS-USB-Tool-vX.Y.Z-x86_64.AppImage
├── SHA256SUMS
├── SHA256SUMS.sig
├── package-repository-snapshot.tar.zst
├── hardware-qualification.md
├── known-issues.md
└── release-notes.md
```

The exact package formats can change once the implementations are built; this file describes the intended release contract rather than claiming these files currently exist.
