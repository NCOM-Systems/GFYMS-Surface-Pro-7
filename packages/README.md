# GFYMS native Arch package family

GFYMS packages should remain normal Arch packages wherever possible. Surface-specific code should integrate with Linux kernel interfaces and normal desktop APIs rather than carrying Windows driver binaries.

## Package groups

| Package | Role |
|---|---|
| `gfyms-surface-platform` | Surface identity, SAM/platform helpers and shared quirks |
| `gfyms-surface-ipts` | IPTS/Touch integration and policy |
| `gfyms-surface-pen` | Surface Pen helpers and diagnostics |
| `gfyms-surface-typecover` | Type Cover detection, attach/detach and policy |
| `gfyms-surface-audio` | Surface-specific Intel SST/SoundWire/Realtek configuration |
| `gfyms-surface-power` | Surface power/thermal/runtime-policy integration |
| `gfyms-surface-sensors` | ISH/IIO/rotation integration |
| `gfyms-surface-dock` | USB-C/DP/MST/USB4/Thunderbolt Surface policy |
| `gfyms-ipu4` | SP7 IPU4/IPU4P support components |
| `gfyms-camera` | Surface camera userspace and diagnostics |
| `gfyms-camera-tuning` | Lawfully redistributable camera tuning assets and conversion tooling |
| `gfyms-surface-daemon` | D-Bus discovery/policy/diagnostics service |
| `gfyms-kde-surface` | KDE Plasma KCM and Plasma integration |
| `gfyms-hello` | Local IR face-authentication stack |
| `gfyms-firmware` | Firmware inventory and safe update integration |
| `gfyms-exe-runner` | Guarded Windows userspace compatibility/extraction layer |
| `gfyms-tools` | `gfyms doctor`, hardware reports and support tooling |

## Repository policy

Each package must have:

- a native Arch packaging recipe
- an explicit source/license record
- reproducible version metadata
- a changelog entry
- install/remove/upgrade tests
- a hardware acceptance test where the package touches physical hardware
- no accidental inclusion of proprietary Windows `.sys`, `.dll`, `.exe` or firmware blobs

Package provenance and third-party license files belong in the package's source tree.