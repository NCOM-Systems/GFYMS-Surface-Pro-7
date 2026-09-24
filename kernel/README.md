# GFYMS Surface kernel layer

The kernel layer is where actual hardware-driver work belongs.

## Rule

Windows `.sys` drivers do not get loaded into the Linux kernel. GFYMS should carry Linux patches/configuration/quirks and upstream contributions that make the Surface hardware work through normal Linux subsystems.

## Expected kernel areas

- Surface Aggregator / SAM
- Surface DTX and hotplug
- IPTS / ITHC
- Surface Type Cover and HID quirks
- Surface Serial Hub / DMA suspend behavior
- Intel ISH
- IPU4/IPU4P camera
- UCSI / USB4 / Thunderbolt
- Intel audio / SOF / SoundWire dependencies
- ACPI/platform profile/power-management

## Provenance

The `extracted/` Windows corpus can document hardware identities and expected device relationships. Kernel patches must describe the Linux-side mechanism and include a reasoned regression test.