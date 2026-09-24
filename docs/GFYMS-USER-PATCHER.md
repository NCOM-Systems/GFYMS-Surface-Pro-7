# GFYMS manual Arch patcher

## Who this is for

This path is for people who already have Arch Linux or an Arch-based distribution installed on a Microsoft Surface Pro 7 and want to add the GFYMS fixes without reinstalling the OS.

## Intended workflow

```text
Existing Arch Linux
        |
        v
   GFYMS Patcher
        |
        +--> detect SP7
        +--> snapshot boot/kernel/config
        +--> refresh GFYMS package metadata
        +--> install/update native GFYMS packages
        +--> configure KDE integration
        +--> enable services
        +--> run hardware diagnostics
        +--> produce report
        v
   reboot when required
        |
        v
   gfyms doctor
```

## What it should fix

The patcher is intended to make it easy to consume GFYMS improvements for:

- Surface Aggregator/platform integration
- IPTS touch
- Surface Pen
- Type Cover and keyboard backlight
- IPU4/IPU4P camera
- Intel audio
- Bluetooth and Wi-Fi integration
- battery/power/thermal policy
- ISH sensors and rotation
- suspend/resume quirks
- USB-C/dock support
- KDE Plasma integration
- GFYMS Hello
- firmware inventory

An individual release may contain only a subset. The patcher must report exactly what changed.

## User-facing safety warning

The project should retain the project's deliberately informal personality, but the technical warning needs to be unambiguous:

> **SOFT WARNING:** This is community-built software for your own Surface hardware. I do not own Microsoft, Windows, Surface, or the third-party software/firmware included by their respective vendors. GFYMS does not claim ownership of their intellectual property, and the project is not affiliated with Microsoft. This project is not a commercial Microsoft driver distribution. Some vendor components may need to be obtained by you from an authorized source. I am not promising permanent maintenance or support. Things can break, and you should keep backups and a recovery path. I am not selling this. If this project helps you, support my other projects, give credit where credit is due, contribute fixes responsibly, and please don't be a dick.

## No automatic firmware flashing

Firmware operations are a separate trust boundary. The patcher should inventory firmware and identify supported update mechanisms first. It should never silently flash a Surface, dock, pen, UEFI or controller firmware image merely because a vendor file exists in the research corpus.

## Rollback

Before changing boot-critical components, record:

- kernel version
- initramfs configuration
- bootloader entries
- installed GFYMS package versions
- relevant kernel command line
- current firmware versions

A failed patch should leave enough information for the user to boot the previous configuration.