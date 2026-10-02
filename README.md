<p align="center">
  <img src="./GFYMS_concept_logo-removebg-preview.png" alt="GFYMS Surface Pro 7" width="360">
</p>

<h1 align="center">GFYMS Surface Pro 7</h1>

<p align="center"><strong>An Arch-based Linux system built around the Microsoft Surface Pro 7.</strong><br>
Native Linux hardware work first. Narrow compatibility layers where they earn their place. Evidence before claims.</p>

<p align="center">
  <a href="https://github.com/NCOM-Systems/GFYMS-Surface-Pro-7/actions"><img src="https://img.shields.io/github/actions/workflow/status/NCOM-Systems/GFYMS-Surface-Pro-7/build-gfyms-release.yml?label=ISO%20build" alt="ISO build status"></a>
  <a href="https://github.com/NCOM-Systems/GFYMS-Surface-Pro-7/releases"><img src="https://img.shields.io/github/v/release/NCOM-Systems/GFYMS-Surface-Pro-7?display_name=tag&label=latest%20release" alt="Latest release"></a>
  <a href="https://archlinux.org/"><img src="https://img.shields.io/badge/base-Arch%20Linux-1793d1" alt="Arch Linux"></a>
  <a href="https://www.kernel.org/"><img src="https://img.shields.io/badge/kernel-Linux-fcc624?logo=linux&logoColor=black" alt="Linux kernel"></a>
  <a href="https://github.com/NCOM-Systems/GFYMS-Surface-Pro-7/blob/main/LICENSE-GFYMS.txt"><img src="https://img.shields.io/badge/license-GFYMS%20%2B%20third--party%20terms-555" alt="License information"></a>
</p>

<p align="center">
  <a href="https://github.com/NCOM-Systems/GFYMS-Surface-Pro-7/releases"><img src="https://img.shields.io/badge/download-releases-202a35?style=for-the-badge" alt="Download releases"></a>
  <a href="./docs/README.md"><img src="https://img.shields.io/badge/read-documentation-0f766e?style=for-the-badge" alt="Read documentation"></a>
  <a href="https://github.com/NCOM-Systems/GFYMS-Surface-Pro-7/discussions"><img src="https://img.shields.io/badge/join-discussions-2563eb?style=for-the-badge" alt="Join discussions"></a>
</p>

> **Current status — preview engineering build.** The single-file ISO pipeline, native package foundation, GFYMS Center, recovery tooling, thermal policy, desktop theme, and WinRunner contract tests are present. Complete Surface Pro 7 hardware qualification, IPU4 camera support, native Android boot, and arbitrary Windows driver execution are not finished.

## Find the right page

- **I want to try the ISO:** [Releases](https://github.com/NCOM-Systems/GFYMS-Surface-Pro-7/releases) · [ISO build and verification](./docs/GFYMS-ISO-LOCAL-BUILD.md)
- **I want to understand support:** [Hardware contract](./docs/GFYMS-HARDWARE-CONTRACT.md) · [Full port matrix](./docs/GFYMS-FULL-SURFACE-PORT-MATRIX.md)
- **I want the technical architecture:** [Build stack](./docs/GFYMS-BUILD-STACK.md) · [Architecture diagram](./docs/diagrams/gfyms-architecture.png)
- **I want to use GFYMS Center:** [Center guide](./docs/GFYMS-CENTER.md) · [Pen Center](./docs/GFYMS-PEN-CENTER.md)
- **I want to understand WinRunner:** [Native Windows runtime](./docs/GFYMS-NATIVE-WINDOWS-RUNTIME.md) · [WDM/IRP contract](./docs/GFYMS-WDM-IRP-CONTRACT.md)
- **I want Android/APK support:** [Native Android plan](./docs/GFYMS-NATIVE-ANDROID.md)
- **I want recovery or cloud storage:** [Recovery flow](./docs/GFYMS-CENTER.md#rollback) · [Nextcloud reference](./cloud/nextcloud/README.md)
- **I want every document in one index:** [Documentation hub](./docs/README.md)

## What GFYMS is

GFYMS means **Go Fix Your Microsoft Surface**. It is an independent Arch-based distribution layer for making the Surface Pro 7 more observable, usable, diagnosable, and recoverable.

The project does not repackage Windows, claim Microsoft affiliation, or pretend that a filename in an extracted installer equals Linux support. The public ISO contains GFYMS-authored code, normal Arch packages, and research-backed manifests. Proprietary Microsoft payloads remain subject to provenance, license, hash, and user-approval rules.

## The compatibility stack

```text
┌─────────────────────────────────────────────────────────────────────┐
│ User experience                                                     │
│ KDE Plasma · GFYMS Center · Surface KCM · diagnostics · recovery    │
├─────────────────────────────────────────────────────────────────────┤
│ GFYMS services                                                      │
│ surface policy · pen controls · thermal policy · updates · staging  │
├─────────────────────────────────────────────────────────────────────┤
│ Linux hardware boundary                                             │
│ kernel · ACPI · SAM/DTX · IPTS/ITHC · HID · IIO/ISH · V4L2/IPU4    │
│ DRM/i915 · ALSA/SOF/SoundWire · power_supply · TPM · BlueZ         │
├─────────────────────────────────────────────────────────────────────┤
│ Optional, isolated compatibility work                              │
│ WinRunner NT/WDM/WDF contracts · AOSP/ART/Bionic/Binder design      │
├─────────────────────────────────────────────────────────────────────┤
│ Build and recovery                                                  │
│ ArchISO · signed-package path · evidence-first repair · cloud vault │
└─────────────────────────────────────────────────────────────────────┘
```

The order matters. Linux remains responsible for hardware safety. GFYMS owns device policy and integration. WinRunner is an experimental contract layer, not the Microsoft Windows kernel. Android is a future optional userspace, not Waydroid, Anbox, a VM, or a fake Pixel profile.

![GFYMS system architecture](./docs/diagrams/gfyms-architecture.png)

## Feature map

### Surface hardware

| Area | What GFYMS has today | Qualification still required |
|---|---|---|
| Platform and power | Thermal engine foundation, power policy, firmware inventory direction | Long-duration battery, thermal, suspend, dock, and firmware tests on SP7 |
| Pen and touch | Center controls and low-latency pen design contract | GFYMS-owned IPTS capture, timestamping, calibration, palm rejection, and measured latency |
| Type Cover | Hardware target and integration path | Attach/detach, keyboard, touchpad, and backlight tests |
| Cameras | IPU4/IPU4P research and port matrix | Front, rear, IR, libcamera/V4L2, exposure, and suspend tests |
| Audio and sensors | ALSA/SOF/SoundWire/IIO/ISH integration direction | Mic, speakers, rotation, ambient light, and suspend tests |

### Desktop and recovery

- **GFYMS Center** — native Qt control plane for Surface status, pen settings, updates, rollback, diagnostics, feedback, and first-run onboarding.
- **Branded desktop theme** — dark GFYMS color tokens, Breeze-compatible fallback, and the NCOM Systems white SVG mark.
- **Evidence-first recovery** — captures service failures, boot errors, package state, disk state, settings, and a reviewable repair plan without silently destroying data.
- **Single-file ISO releases** — GitHub Actions publishes one complete ISO artifact instead of fragments.
- **Private cloud vault** — a Nextcloud Docker reference for selective sync, cold-file offload, and encrypted recovery snapshots. It is not remote RAM, swap, or boot storage.

### Compatibility and runtimes

- **WinRunner** — PE32+ AMD64 parsing, relocations, bounded memory, tagged pool allocations, named objects, handles, events, WDM device objects, dispatch tables, IRPs, and completion routines. It does not yet execute arbitrary `.sys` files.
- **.NET strategy** — managed Windows applications are treated as user-mode compatibility work, separate from kernel-driver contracts.
- **Native Android direction** — optional x86_64 AOSP-derived userspace with ART, Bionic, Binder, framework services, and GFYMS hardware adapters. APK support is not in the base ISO yet.
- **F-Droid direction** — planned as an Android-subsystem application source, not a Linux desktop package.

### Optional Find My bridge

<p>
  <img src="./assets/gfyms-findmy-bridge.svg" alt="GFYMS Find My bridge icon" width="72" align="left" style="margin-right:16px">
  <strong>GFYMS Find My Bridge</strong><br>
  An optional OpenHaystack-compatible Bluetooth LE beacon service.
</p>

This is a **GFYMS-owned compatibility mark**, not Apple’s official Find My logo. The bridge is not Apple-certified hardware, does not register the Surface through an Apple public API, and does not guarantee location retrieval. See [the bridge documentation](./docs/GFYMS-FIND-MY.md), [OpenHaystack](https://github.com/seemoo-lab/openhaystack), and Apple’s official [Find My overview](https://www.apple.com/icloud/find-my/).

<p><a href="https://www.apple.com/icloud/find-my/"><img src="https://img.shields.io/badge/official-Apple%20Find%20My%20overview-1d1d1f?style=for-the-badge" alt="Official Apple Find My overview"></a></p>

## Project history and next chapters

The detailed source for this timeline is [`docs/gfyms-timeline.json`](./docs/gfyms-timeline.json). GFYMS Center reads the same file when it is available, so the desktop update view and this page can point to the same project history.

| Date | Milestone | State |
|---|---|---|
| 2026-09-25 | WinRunner NT/WDM compatibility contracts began | Implemented foundation |
| 2026-09-26 | Surface Pro 7 MSI research corpus restored | Research input |
| 2026-09-28 | Recovery, thermal, build, and distro documentation baseline | Implemented foundation |
| 2026-09-29 | Native Android architecture and low-latency pen direction documented | Planned architecture |
| 2026-09-30 | Single-file ISO release path verified | Implemented and CI-tested |
| 2026-09-30 | OpenHaystack-compatible Find My bridge added | Experimental |
| 2026-10-01 | NCOM white SVG branding and VM/asset audit added | Implemented documentation/assets |
| 2026-10-02 | GFYMS Center wizard and branded desktop theme shipped | Implemented and packaged |
| Next | Qualify Surface platform, pen, Type Cover, sensors, audio, and IPU4 camera paths | Hardware work |
| Next | Add WinRunner MDL/DMA, PnP, power, interrupts, WDF, and controlled DriverEntry tests | Experimental engineering |
| Next | Build the removable native Android proof of concept and F-Droid path | Planned |
| Next | Harden Secure Boot/UKI, signed releases, recovery media, and restore fixtures | Planned |

## Release and verification

The release workflow publishes the complete ISO as the `GFYMS-Surface-Pro-7-preview-release` artifact. Download the single ISO from the Actions run or use a tagged release when available; do not assemble fragments.

```bash
sha256sum -c ISO-SHA256SUM
```

For a local build:

```bash
./tools/build-gfyms-release-local.sh
```

Before calling a build supported, run the repository checks and then qualify the actual Surface hardware. A passing VM build is not proof of working cameras, pen, Type Cover, audio, firmware, or suspend/resume.

## Documentation hub

The [documentation hub](./docs/README.md) is organized by user question, not by file name. These are the primary paths:

| Topic | Document |
|---|---|
| Build and release | [ISO local build](./docs/GFYMS-ISO-LOCAL-BUILD.md) · [Release plan](./docs/GFYMS-RELEASE-PLAN.md) · [Build stack](./docs/GFYMS-BUILD-STACK.md) |
| Hardware support | [Hardware contract](./docs/GFYMS-HARDWARE-CONTRACT.md) · [Full port matrix](./docs/GFYMS-FULL-SURFACE-PORT-MATRIX.md) |
| Desktop | [Center](./docs/GFYMS-CENTER.md) · [KDE integration](./docs/GFYMS-KDE-PLASMA-INTEGRATION.md) · [Pen Center](./docs/GFYMS-PEN-CENTER.md) · [Pen latency](./docs/GFYMS-PEN-LATENCY-PLAN.md) |
| Runtime contracts | [ABI contracts](./docs/GFYMS-ABI-CONTRACTS.md) · [WDM/IRP](./docs/GFYMS-WDM-IRP-CONTRACT.md) · [WinRunner](./docs/GFYMS-NATIVE-WINDOWS-RUNTIME.md) · [WinKIT](./docs/WINKIT-IMPLEMENTED.md) |
| Android and managed runtimes | [Native Android](./docs/GFYMS-NATIVE-ANDROID.md) · [.NET runtime](./docs/GFYMS-DOTNET-RUNTIME.md) |
| Recovery and cloud | [Recovery source](./packages/gfyms-surface/recovery/gfyms-recovery.py) · [Nextcloud reference](./cloud/nextcloud/README.md) |
| Provenance and law | [Legal boundary](./docs/LEGAL-AND-DISTRIBUTION.md) · [MS API Clone](./docs/MS-API-CLONE.md) · [Integration plan](./docs/MS-API-CLONE-INTEGRATION.md) |
| Testing history | [R0.01DEV audit](./docs/R0.01DEV-VM-ASSET-AUDIT.md) · [Original VM report](./RANTS/R0.01DEV/R0.01DEV.md) |

## Repository map

- [`kernel/`](./kernel/) — WinRunner and kernel contract work
- [`packages/`](./packages/) — GFYMS packages and installed services
- [`profiles/`](./profiles/) — ArchISO profiles
- [`tools/`](./tools/) — builders, inspection, staging, and recovery helpers
- [`docs/`](./docs/) — architecture, contracts, qualification, legal notes, and timeline
- [`assets/`](./assets/) — approved and provisional branding assets
- [`extracted/`](./extracted/) — local research corpus, not an automatic redistribution bundle

## Legal and naming boundary

GFYMS is independent and is not affiliated with Microsoft or Apple. Surface, Windows, Find My, Android, Google Pixel, and related marks belong to their respective owners. GFYMS uses those names to describe target hardware, compatibility boundaries, or external references.

The extracted Microsoft packages are research and provenance inputs. They are not automatically redistributable. GFYMS-authored source, derived manifests, and native Linux implementations must remain distinguishable from third-party payloads and their licenses. Read [the legal and distribution boundary](./docs/LEGAL-AND-DISTRIBUTION.md) before adding vendor binaries or logos.

## Contributing

Please include the Surface model, firmware, kernel and GFYMS versions, exact reproduction steps, sanitized diagnostics, and whether the result came from a VM or real Surface Pro 7. Separate what you observed from what you propose.

Keep the frustration. Turn it into reproducible evidence and a patch.
