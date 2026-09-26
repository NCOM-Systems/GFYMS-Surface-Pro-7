# GFYMS Windows-kernel compatibility layer

This directory is the research implementation of the Windows NT/WDM/WDF compatibility boundary used by GFYMS.

The first milestone is deliberately narrow: define and test a stable Linux-side ABI boundary before attempting to execute arbitrary Windows kernel code.

## Planned layers

1. PE/COFF parsing and relocation
2. import/export resolution
3. NT executive primitives
4. WDM objects and IRPs
5. PnP and power
6. memory, MDLs and DMA
7. interrupts, DPCs and work items
8. PCI and ACPI resource translation
9. registry/configuration
10. KMDF compatibility

Target behavior is derived from the import inventories and dynamic observations produced by tools/gfyms-native-re/.

The loader must remain explicitly opt-in and test-only until a target driver has passed hardware qualification.
