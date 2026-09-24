# GFYMS Surface Pro 7

**Go Fix Your Microsoft Surface.**

GFYMS is evolving from a Surface Pro 7 Windows-driver reverse-engineering repository into an Arch-based Surface Pro 7 enablement stack and bootable OS project.

The original project was a rage project: take a Surface Pro 7 that is annoying under Linux, figure out exactly what Microsoft ships for the hardware, and build the missing pieces as native Linux software so the machine is actually pleasant to use.

GFYMS is independent and is not affiliated with Microsoft.

## What GFYMS is building

The target is a full Surface Pro 7 hardware contract:

- IPTS touchscreen and pen
- detachable Type Cover, touchpad and keyboard backlight
- Intel IPU4/IPU4P camera stack
- front OV5693, rear OV8865 and IR OV7251 camera support
- **GFYMS Hello** — a native Linux, Windows-Hello-style face-authentication experience using the SP7 IR camera
- Intel SST/SoundWire/Realtek audio
- Wi-Fi and Bluetooth
- battery, charging, thermal and power-management integration
- accelerometer, ambient-light sensing and automatic rotation
- USB-C, DisplayPort, MST and dock/USB4/Thunderbolt behavior
- TPM and firmware inventory/update integration
- optional fingerprint support when the exact sensor is supported
- a guarded Windows `.EXE` compatibility/extraction runner
- Surface-specific diagnostics and hardware-in-the-loop tests

See docs/GFYMS-HARDWARE-CONTRACT.md for the acceptance contract.

## Reverse-engineering corpus

The extracted/ tree is the research/provenance corpus produced from the Surface Pro 7 Windows MSI. It is useful for identifying hardware IDs, firmware relationships, package structure and configuration clues.

It is **not** automatically a redistributable software bundle.

GFYMS's legal distribution boundary is documented in docs/LEGAL-AND-DISTRIBUTION.md. In particular, ownership of a Surface Pro 7 does not by itself grant a public license to redistribute Microsoft's copyrighted Windows drivers, DLLs, EXEs or firmware.

The OS should therefore ship GFYMS-authored Linux code and properly licensed third-party components, while vendor-specific material is acquired only through a lawful source when required.

## GFYMS Hello

Microsoft identifies the Surface Pro 7 as having a dedicated Windows Hello facial-recognition camera.

The GFYMS implementation is intentionally **not** Microsoft's Windows Hello software. It is a Linux-native authentication layer built around:

`OV7251 IR camera -> IPU4/IPU4P -> libcamera -> local face/authentication engine -> PAM`

The design keeps passwords available as recovery, keeps biometric data local, and leaves the recognition backend replaceable.

See docs/GFYMS-HELLO.md.

## OpenFactory image path

profiles/openfactory-surface-pro-7.json is the initial OpenFactory-oriented image profile for the project.

It captures the target base image, package set, custom GFYMS package family, hardware intent and smoke-test scenarios. It is a project profile and should be normalized/validated against the current OpenFactory recipe schema before being treated as a production build recipe.

OpenFactory's current workflow separates recipe validation, image building, VM testing and physical-hardware qualification. GFYMS follows the same model: VM evidence proves the image, while a real Surface Pro 7 proves Surface hardware behavior.

## MSI extraction

This repository currently uses nightlark/pymsi to inspect and extract the Surface Pro 7 Windows 11 MSI.

The extraction workflow preserves:

- the source MSI
- parsed MSI tables
- OLE streams
- extracted files
- pymsi reports
- manifests, hashes and inventory metadata

The MSI itself is not executed by the workflow.

## Current status

The reverse-engineering corpus is in place. The next engineering phase is to turn the observed Windows hardware contract into native Arch packages and hardware tests, starting with the components that have the strongest Surface-specific evidence:

1. IPU4/IPU4P camera
2. IPTS/touch/pen
3. Type Cover
4. Intel audio
5. ISH sensors and rotation
6. suspend/resume and power
7. GFYMS Hello
8. docks/USB-C/USB4/Thunderbolt
9. firmware inventory/update support
10. fingerprint and `.EXE` compatibility layers

## License

GFYMS-authored material is covered by LICENSE-GFYMS.txt.

Third-party material remains under its own license or terms. The license for GFYMS-authored code does not grant rights to Microsoft or other third-party software and firmware.