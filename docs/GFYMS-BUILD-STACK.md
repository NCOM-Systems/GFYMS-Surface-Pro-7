# GFYMS Arch build stack

## Layer model

```text
Arch Linux
   |
   +--> KDE Plasma / KWin / SDDM
   |
   +--> Linux kernel + linux-firmware
   |       |
   |       +--> Surface platform / SAM / DTX
   |       +--> IPTS / ITHC
   |       +--> HID / USB / Type Cover
   |       +--> IIO / ISH
   |       +--> DRM / i915
   |       +--> UCSI / USB4 / Thunderbolt
   |       +--> ALSA / SOF / SoundWire
   |       +--> IPU4/IPU4P camera stack
   |
   +--> GFYMS native services
   |       +--> gfyms-surface-daemon
   |       +--> gfyms-tools
   |       +--> gfyms-power
   |       +--> gfyms-camera
   |       +--> gfyms-hello
   |
   +--> KDE integration
   |       +--> gfyms-kde-surface
   |       +--> Surface KCM
   |       +--> Plasma status
   |
   +--> package repository
   |
   +--> ArchISO profile
   |
   +--> USB tool
   |
   +--> physical SP7 qualification
```

## Native-driver principle

GFYMS can provide Linux kernel patches, device quirks, udev rules, system services, firmware metadata, user-space tools and KDE integration. It should not attempt to load Microsoft Windows `.sys` drivers in Linux.

Windows `.sys` files belong to the Windows kernel driver model. The `.EXE` runner is therefore a compatibility/extraction feature for appropriate user-space or installer software, not a magic Windows-kernel compatibility layer.

## Package family

Planned package names:

- `gfyms-surface-platform`
- `gfyms-surface-ipts`
- `gfyms-surface-pen`
- `gfyms-surface-typecover`
- `gfyms-surface-audio`
- `gfyms-surface-power`
- `gfyms-surface-sensors`
- `gfyms-surface-dock`
- `gfyms-ipu4`
- `gfyms-camera`
- `gfyms-camera-tuning`
- `gfyms-surface-daemon`
- `gfyms-kde-surface`
- `gfyms-hello`
- `gfyms-firmware`
- `gfyms-exe-runner`
- `gfyms-tools`

These names are project targets, not claims that the packages already exist in a public repository.