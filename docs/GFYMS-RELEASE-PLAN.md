# GFYMS release artifacts

The project should eventually publish three primary user-facing artifacts.

## 1. GFYMS Arch Surface Patcher

Target: users who already run Arch Linux or an Arch-based distribution on a Surface Pro 7.

Purpose:

- detect Surface Pro 7 hardware
- snapshot relevant configuration
- install or update GFYMS packages
- install kernel/configuration components required by the release
- enable required services
- configure KDE integration
- run `gfyms doctor`
- produce a rollback/report bundle

Safety requirements:

- refuse to run on unsupported hardware unless explicitly overridden
- never overwrite an unrelated kernel without a clear backup path
- use signed packages where available
- verify package hashes
- show every change before applying it when interactive
- preserve the user's existing bootloader configuration
- provide an uninstall/rollback path
- never silently flash firmware

## 2. Official GFYMS Arch Surface ISO

Target: clean installation on Surface Pro 7.

Baseline:

- Arch Linux base
- KDE Plasma
- Wayland
- SDDM
- NetworkManager
- PipeWire/WirePlumber
- BlueZ
- linux-firmware
- Surface-specific GFYMS package set
- GFYMS KDE integration
- Surface diagnostics
- camera stack
- sensor stack
- firmware inventory
- TPM tooling
- optional GFYMS Hello

ArchISO is the appropriate low-level image technology for a native Arch ISO. Its profile structure supports package lists, custom files and custom repositories, and `mkarchiso` builds the resulting bootable image. citeturn568345search1turn568345search9

## 3. GFYMS USB Tool

The USB tool should make writing and verifying the ISO easy without pretending to be a firmware flasher.

Modes:

```text
GFYMS USB Tool
  |
  +--> Discover removable drives
  +--> Verify ISO SHA-256
  +--> Verify signature
  +--> Confirm target drive
  +--> Write image
  +--> Sync / flush
  +--> Verify written blocks
  +--> Show recovery instructions
```

Linux-native implementation should eventually use a small privileged helper rather than giving the GUI broad root access.

## Release channels

- `stable` — tested on physical SP7 hardware
- `testing` — newer kernel/package combinations
- `nightly` — experimental camera, Hello and platform work

Every release should publish:

- ISO
- SHA-256
- signature
- package repository snapshot
- hardware-qualification report
- known-issues report
- release notes

## Hardware qualification

An ISO should not be labeled Surface-qualified merely because it boots in a VM. Physical qualification must test the Surface contract on an actual SP7.