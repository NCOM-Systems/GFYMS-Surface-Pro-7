# GFYMS Surface Pro 7 hardware contract

This document defines what the OS should consider "Surface Pro 7 support". A green build means the requested software is present; a green physical qualification means the behavior was actually tested on SP7 hardware.

## Core contract

| Capability | Target behavior | Evidence source / implementation direction |
|---|---|---|
| Display | Native 2736x1824 panel, brightness, DPMS | i915/DRM + Surface platform |
| IPTS touchscreen | Multi-touch, palm rejection, suspend/resume | Linux Surface IPTS stack + iptsd |
| Surface Pen | Pressure, buttons, hover, stable event delivery | HID/IPTS + pen protocol/firmware metadata |
| Type Cover | Attach/detach, keyboard, touchpad, media keys | USB HID + Surface-specific quirks |
| Keyboard backlight | Brightness state follows attach/power state | SurfaceKeyboardBacklight path |
| Front camera | OV5693 RGB | IPU4/IPU4P + libcamera |
| Rear camera | OV8865 RGB | IPU4/IPU4P + libcamera |
| IR camera | OV7251 for face authentication | IPU4/IPU4P + GFYMS Hello |
| Microphones | Dual far-field mics | Intel SST/SoundWire/ALSA/PipeWire |
| Speakers/headphone | Working playback with correct topology | SOF/HDA/SoundWire/Realtek |
| Wi-Fi | Intel Wi-Fi 6 | Linux iwlwifi/linux-firmware |
| Bluetooth | Stable suspend/resume and recovery | btusb/btintel + firmware |
| Battery | Charge/discharge/health reporting | Surface battery/SAM/Linux power supply |
| Power | Runtime PM, thermal behavior, platform profiles | Surface platform + ACPI + cpufreq |
| Suspend | Reliable s2idle and resume | kernel Surface quirks + device-specific fixes |
| Accelerometer | IIO sensor available | Intel ISH + Surface/SAM integration |
| Ambient light | ALS exposed to desktop | Surface Light Sensor + IIO |
| Auto rotation | Rotation follows physical orientation | sensor + iio-sensor-proxy/desktop |
| USB-C | USB data + DP Alt Mode | USB-C/DRM/UCSI |
| External displays | Stable multi-monitor/dock operation | DRM + Type-C + MST |
| microSD | Hotplug/read/write | card reader driver |
| TPM | Present and usable | tpm2-tss/tools |
| Firmware | Inventory/version reporting and safe updates | fwupd where supported |
| Surface Connect | Accessories/docks work | Surface-specific ecosystem support |
| Docks | Dock firmware/update awareness | UCSI/USB4/TB + vendor firmware policy |
| Fingerprint | Hardware-dependent optional target | libfprint/fprintd |
| Windows Hello-style face unlock | IR enrollment/authentication | GFYMS Hello |
| .EXE runner | Safely classify/extract user-supplied Windows software | GFYMS compatibility layer |
| Managed Windows runtime | Modern .NET, legacy .NET Framework compatibility, and Wine/Wine-Mono fallback | GFYMS user-mode runtime |
| Windows driver ABI | Research/execute selected x86_64 Windows drivers through GFYMS NT/WDM/WDF compatibility | Test-only compatibility layer |

## Priority implementation layers

### Tier 0 — boot and identity

- Surface UEFI awareness
- kernel command line / initramfs
- Surface Aggregator
- battery/charger
- display
- keyboard
- network
- basic USB-C

### Tier 1 — daily Surface usability

- IPTS touch
- Surface Pen
- Type Cover + touchpad
- keyboard backlight
- Bluetooth
- audio
- power/thermal policy

### Tier 2 — historically hard hardware

- IPU4/IPU4P camera stack
- IR camera path
- GFYMS Hello
- ISH accelerometer
- ambient light / rotation
- suspend/resume stress handling

### Tier 3 — ecosystem and recovery

- USB-C/DP Alt Mode
- MST/docking
- Thunderbolt/USB4 docks
- firmware inventory/update workflows
- fingerprint investigation
- .EXE classification/runner
- managed .NET / legacy .NET Framework runtime selection
- selected Windows-driver NT/WDM/WDF compatibility research

## Hardware-in-the-loop rule

VM tests can validate image construction, package presence, service startup, and user-space behavior. They cannot prove IPTS, IPU4, SAM, ISH, Type Cover, camera, firmware, or suspend behavior on a physical SP7.

GFYMS should therefore maintain a real Surface Pro 7 test machine as a hardware-in-the-loop target and publish test evidence for each capability.