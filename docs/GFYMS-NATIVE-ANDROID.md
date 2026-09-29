# GFYMS Native Android Subsystem

## Decision

GFYMS will **not** use Waydroid, Anbox, a full Android virtual machine, or a fake Google Pixel device profile.

The target is a first-class, optional Android subsystem built from open Android/AOSP source and integrated with the GFYMS Linux kernel and Surface hardware adapters. It must run as native x86_64 Linux processes on the GFYMS kernel. “Native” here means no guest VM and no Android guest kernel; it does **not** mean that Android application bytecode can run without an Android runtime.

An APK is a package containing DEX bytecode, resources, manifests, and sometimes native ELF libraries. To run it correctly, GFYMS must provide Android's application model and runtime rather than attempting to execute the APK as an ordinary Linux ELF program.

## Required native stack

```text
APK
  |
  +--> Package Manager / installd / permissions / app sandbox
  +--> ActivityManager / WindowManager / services
  +--> ART (DEX execution, JIT/AOT, garbage collection)
  +--> Bionic libc + Android native libraries
  +--> Binder IPC + binderfs
  +--> SurfaceFlinger + HWComposer + graphics allocator
  +--> AOSP HAL services using AIDL interfaces
  +--> GFYMS Android adapters
  +--> GFYMS Linux drivers and Surface hardware
  |      +--> Surface Aggregator / SSH
  |      +--> HID / IPTS / pen / Type Cover
  |      +--> IIO / ISH / light / accelerometer
  |      +--> V4L2 / libcamera / IPU4
  |      +--> ALSA / SOF / SoundWire / PipeWire bridge
  |      +--> DRM / i915 / Mesa / Vulkan
  |      +--> power_supply / thermal / USB-C / Bluetooth
  +--> Linux kernel
```

The Android Developers platform architecture identifies the Linux kernel, HAL, ART, native libraries and Java API framework as separate layers. GFYMS should implement the missing device-specific HAL layer instead of importing Pixel HALs or Windows drivers.

## GFYMS adapter modules

The first implementation should be an AIDL-oriented adapter tree, kept separate from the core Arch desktop:

- `android/gfyms-hal-common` — device identity, permissions, logging and capability discovery
- `android/gfyms-camera-hal` — Android camera provider/Camera HAL3 adapter over GFYMS V4L2/libcamera
- `android/gfyms-sensors-hal` — sensors HAL over GFYMS IIO/ISH and Surface Aggregator events
- `android/gfyms-audio-hal` — Android Audio HAL over ALSA/SOF/SoundWire; use PipeWire only as an explicit bridge where routing requires it
- `android/gfyms-power-hal` — battery, charging, thermal and power-profile state over Linux power_supply and GFYMS policy
- `android/gfyms-input` — touchscreen, pen, keyboard and touchpad event translation with no duplicate device ownership
- `android/gfyms-graphics` — DRM/i915/Mesa-backed gralloc, HWComposer and SurfaceFlinger integration
- `android/gfyms-bluetooth` — BlueZ-backed Android Bluetooth service adapter
- `android/gfyms-surface-service` — optional Binder service exposing qualified Surface-specific controls to Android apps

Every adapter must declare the Linux devices it opens, the Android interface version it implements, its ownership model, failure behavior, and a hardware test fixture. The desktop Linux stack remains authoritative for the device; Android adapters must not race the desktop for cameras, audio, input, or sensors.

## Kernel requirements

The GFYMS kernel must provide the actual primitives needed by the Android userspace:

- Binder IPC and binderfs with private device instances
- memfd/shared-memory primitives and synchronization
- namespaces, cgroups and seccomp for app isolation
- futexes, epoll, eventfd and robust filesystem semantics
- DRM render nodes and DMA-BUF for graphics buffers
- V4L2/media-controller interfaces for camera adapters
- IIO and input event interfaces for sensors and input
- ALSA controls and PCM for audio
- Bluetooth HCI and USB support
- SELinux or an equivalently strong MAC policy for Android processes
- a stable x86_64 ABI and reproducible runtime libraries

Do not add Android-only kernel patches just because an old container project expects them. First check whether mainline Linux already provides the required primitive. New GFYMS kernel work must be narrowly scoped, tested, and owned by GFYMS.

## ABI reality

The Surface Pro 7 is x86_64. Native APKs containing `x86_64` libraries can run directly. APKs containing only `arm64-v8a` or `armeabi-v7a` native libraries cannot run natively on this CPU. GFYMS should not hide this with an unreviewed binary translation layer.

The initial support policy should be:

1. Java/Kotlin/Dex-only APKs: target compatibility testing.
2. APKs with `x86_64` native libraries: target native compatibility testing.
3. APKs with x86 plus x86_64 splits: target compatibility testing with the matching ABI selected.
4. ARM-only APKs: report unsupported unless a separately approved, measured, and clearly labeled translation project is added later.
5. Google Mobile Services and Pixel-only proprietary services: not part of the base GFYMS system.

## Surface hardware policy

The Surface Pro 7 must be identified as a GFYMS Surface Pro 7, not a Google Pixel. Android system properties may describe the Android product flavor, but they must not falsify hardware identity, firmware provenance, sensor IDs, camera calibration, or security state.

Surface-derived functionality should flow through native GFYMS implementations:

- Surface Aggregator and SSH provide qualified battery, thermal, buttons and accessory information.
- GFYMS IPTS and HID provide touch, pen, keyboard and touchpad events.
- GFYMS ISH/IIO provides accelerometer and ambient-light data.
- GFYMS IPU4/libcamera provides camera streams and controls.
- GFYMS audio integration provides microphone and playback endpoints.
- DRM/i915/Mesa provides graphics acceleration.

Windows `.sys`, `.dll`, Pixel HALs, Pixel firmware, and Google proprietary services are not substitutes for these adapters.

## Security and lifecycle

The subsystem must be optional and removable. It must not be required for boot, desktop login, recovery, firmware updates, or Surface driver operation.

Android apps must run under separate UIDs and constrained SELinux domains. Binder devices should be private to the Android service group. Installation must verify APK signatures and record package provenance. The desktop user must be able to stop the Android subsystem and reclaim its memory without rebooting.

The recovery system must treat Android separately: preserve its package database and app data only when the user selects them, and never allow an Android update to modify the GFYMS boot or Surface driver state.

## Staged implementation

### Stage 0 — contract and proof of concept

- Add an `android/` build contract and license inventory.
- Build an x86_64 AOSP userspace target from current AOSP sources.
- Boot or start only the minimal framework services in a GFYMS development profile.
- Demonstrate Binder, ART, Bionic, package installation and a signed test APK.
- No camera, audio, sensors or Google services yet.

### Stage 1 — desktop-integrated native runtime

- Add a GFYMS Android service manager and resource limits.
- Implement app install/remove, per-app UID isolation and lifecycle management.
- Provide a minimal SurfaceFlinger/DRM path.
- Add x86_64 APK compatibility reporting and a package capability inspector.

### Stage 2 — Surface adapters

- Add sensors, input, power, audio and camera HALs one at a time.
- Use virtual fixtures before touching physical hardware.
- Qualify each adapter with attach/detach, suspend/resume, hotplug, permission and failure tests.
- Ensure Android and KDE do not concurrently own the same hardware endpoint.

### Stage 3 — optional user feature

- Package the subsystem separately from the base ISO.
- Keep it disabled by default on low-memory systems.
- Offer an explicit enable/disable control in GFYMS Center.
- Publish a tested APK compatibility list rather than claiming universal Android support.

## What this is and is not

This is a native Android userspace integration project. It is not a VM, not Waydroid, not a Pixel port, not Wine, and not a claim that APK source code can execute without ART. It is also not a replacement for native Linux drivers: GFYMS Linux remains the hardware owner, while Android HALs are carefully controlled clients.

## Sources

- [1] https://developer.android.com/guide/platform "Android platform architecture"
- [2] https://source.android.com/docs/core/architecture/hal "AOSP hardware abstraction layer overview"
- [3] https://source.android.com/docs/setup/build/building "AOSP build documentation"
- [4] https://developer.android.com/ndk/guides/abis "Android ABI documentation"
- [5] https://docs.kernel.org/admin-guide/binderfs.html "Linux kernel binderfs documentation"
- [6] https://source.android.com/docs/core/camera/camera3 "AOSP Camera HAL3 documentation"
- [7] https://source.android.com/docs/core/audio/implement "AOSP Audio HAL documentation"
- [8] https://source.android.com/docs/core/interaction/sensors/sensors-hal2 "AOSP Sensors HAL documentation"
