# GFYMS ArchISO Surface Pro 7 profile

This is the native ArchISO profile target for the official GFYMS Surface Pro 7 image.

## Desktop

KDE Plasma is the built-in desktop. The image targets Plasma on Wayland with SDDM and KDE's normal Linux desktop integration. Arch currently packages Plasma through `plasma-meta`; current Arch packaging also includes core components such as System Settings, PowerDevil, BlueDevil and the KDE portal integration. citeturn568345search0turn568345search10

## Build

Install `archiso` on the build host, copy/clone the repository, and run `mkarchiso` against this profile after the GFYMS package repository has been configured.

```bash
sudo pacman -S --needed archiso
sudo mkarchiso -v -w work -o out profiles/archiso-surface-pro-7
```

The exact ArchISO profile layout is intentionally kept close to Arch's documented profile model: package selection is in `packages.x86_64`, while custom package repositories and configuration can be added through the profile's `pacman.conf`. See https://wiki.archlinux.org/title/Archiso.

## Custom GFYMS repository

The commented GFYMS package set is not copied into this ISO by magic. The production image should point pacman at a signed GFYMS repository containing packages built from this project's source.

That prevents the ISO build from depending on unpublished local files and lets the patcher consume the same package artifacts.

## Physical qualification

Booting this ISO in a VM proves the image build. It does not prove Surface hardware support. The release process must run the hardware contract on a real Surface Pro 7 before labeling an ISO as `stable`.