# GFYMS KDE Plasma integration

GFYMS is designed to make the Surface Pro 7 feel like a first-class Linux platform inside KDE Plasma. This is a native Linux integration layer; it is not a mechanism for loading Windows `.sys` drivers into the Linux kernel.

## The correct driver model

Plasma already consumes hardware through Linux kernel and desktop interfaces such as sysfs, udev, input devices, power-management services, PipeWire/ALSA, libcamera, IIO, and D-Bus. GFYMS should integrate with those interfaces instead of creating a parallel pretend-driver stack.

Architecture:

```text
Surface hardware
     |
Linux kernel / drivers
     |
     +--> sysfs / udev / input / IIO / DRM / power_supply
     +--> ALSA / PipeWire
     +--> libcamera
     +--> Surface-specific platform services
                    |
                    v
             gfyms-surface-daemon
                    |
                    +--> D-Bus API
                    +--> device capabilities
                    +--> health / diagnostics
                    +--> Surface policy
                    +--> firmware state
                    |
                    v
             GFYMS KDE integration
                    |
                    +--> KDE System Settings KCM
                    +--> Plasma tray/status
                    +--> power profile integration
                    +--> camera/Hello controls
                    +--> Type Cover/pen controls
                    +--> diagnostics
```

KDE's configuration-module architecture uses KCMs for System Settings and supports QML-based modules for new Plasma integrations. GFYMS should use that mechanism for its Surface-specific controls. See https://develop.kde.org/docs/features/configuration/kcm/.

## `gfyms-surface-daemon`

The daemon is the policy and discovery layer. It should not replace kernel drivers. It should:

- detect the exact Surface Pro 7 variant and hardware IDs
- expose a stable D-Bus interface
- read kernel/udev/IIO/power/camera/audio state
- coordinate Surface-specific quirks and policy
- provide diagnostics used by `gfyms doctor`
- expose safe firmware inventory information
- expose capability state to KDE
- coordinate optional GFYMS Hello services
- record test and health results locally
- avoid requiring telemetry or a network connection for basic operation

## KDE System Settings

Create a dedicated **GFYMS Surface** KCM with pages or cards for:

- **Overview** — Surface model, firmware state, support status
- **Touch & Pen** — IPTS sensitivity, stylus behavior, palm rejection policy
- **Type Cover** — attach state, touchpad behavior and keyboard backlight
- **Power & Battery** — Surface power profile and charging policy
- **Cameras** — front/rear/IR camera status and test controls
- **Audio** — microphone/speaker path diagnostics and profile status
- **Sensors** — accelerometer, ambient light and rotation
- **Docking & USB-C** — dock and external-display state
- **Firmware** — inventory and supported safe update paths
- **GFYMS Hello** — enrollment/status when the feature is installed
- **Diagnostics** — hardware qualification and log collection

These settings should manipulate existing Linux interfaces and GFYMS services. Plasma should not have to understand Microsoft's Windows driver model.

## Plasma session behavior

GFYMS should integrate with existing Plasma components where appropriate instead of replacing them. Arch packages Plasma and its desktop components through the normal Arch repositories, while SDDM provides the display-manager path for Plasma. GFYMS integrates with those native components instead of replacing them. See https://archlinux.org/packages/extra/any/plasma-meta/ and https://archlinux.org/packages/extra/x86_64/sddm/.

That means the GFYMS OS should ship KDE Plasma as a normal Arch component and layer Surface-specific support into it.

## Plasma-visible identity

The user-facing experience should identify the machine as:

```text
GFYMS Surface Pro 7
Microsoft Surface Pro 7 hardware profile
GFYMS Surface integration: Active
```

System Settings should show GFYMS capabilities without claiming that GFYMS is a Microsoft driver package.

## Device discovery

Use a combination of:

- DMI/SMBIOS
- ACPI IDs
- PCI IDs
- USB VID/PID
- HID IDs
- udev properties
- `/sys` state
- kernel driver binding
- Surface Aggregator/SAM state

Device identities from the extracted Windows package are research metadata. The Linux implementation should bind through Linux's own supported interfaces.

## Future KCM package

Planned package:

`gfyms-kde-surface`

Suggested contents:

- `kcms/gfyms_surface/` QML/C++ KCM
- KService/KPackage metadata
- D-Bus client library
- Plasma status component
- translations
- icons
- test utilities
- integration tests

## Acceptance tests

A qualified Plasma image should demonstrate:

1. GFYMS Surface appears in System Settings.
2. The KCM correctly identifies the SP7.
3. Touch and pen status reflects real kernel state.
4. Type Cover attach/detach state is reflected without restarting Plasma.
5. Battery/power state updates live.
6. Camera inventory includes the available SP7 cameras when the camera stack is working.
7. Sensor state is visible when the ISH/IIO path is working.
8. Firmware inventory does not claim support when no safe update path exists.
9. Removing GFYMS user-space services does not make the underlying Linux desktop unusable.