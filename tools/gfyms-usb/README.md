# GFYMS USB Tool

Planned native utility for safely writing official GFYMS ISO releases to removable media.

## Requirements

- verify ISO checksum
- verify release signature
- enumerate removable drives
- clearly distinguish the selected target drive
- require explicit destructive confirmation
- write the image
- flush/sync the device
- verify the resulting media
- provide recovery instructions

## Safety boundary

The USB tool writes disk images. It is not a Surface firmware flasher and must not scan the research corpus and decide to flash arbitrary vendor firmware.

## Example interface

```text
gfyms-usb list
gfyms-usb verify gfyms-surface-pro-7.iso
gfyms-usb write gfyms-surface-pro-7.iso /dev/sdX
gfyms-usb verify-media /dev/sdX
```