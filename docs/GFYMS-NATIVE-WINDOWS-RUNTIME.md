# GFYMS Native Windows Runtime

GFYMS is investigating native execution of selected Windows x86_64 kernel drivers on Linux without a Windows VM and without CPU instruction emulation.

The target is a Linux-side compatibility environment that implements the Windows kernel/driver contracts required by real `.sys` binaries. The driver machine code executes directly on the Surface Pro 7 CPU.

This is not a transplant of Microsoft's NT kernel. It is a Linux implementation of the relevant NT, WDM and WDF contracts.

## Architecture

    Windows SYS PE image
            |
            v
    GFYMS PE loader / relocator
            |
            v
    GFYMS NT compatibility layer
      - object/reference primitives
      - WDM device objects
      - IRPs and I/O stacks
      - PnP / power
      - memory / MDL / DMA
      - interrupts / DPCs
      - timers / work items / synchronization
      - ACPI / PCI resource translation
      - registry/configuration
            |
            +--> WDF compatibility (starting with KMDF)
            |
            v
    Linux kernel subsystems
      - PCI / ACPI / DMA / IOMMU
      - USB / HID / input
      - ALSA / SOF / SoundWire
      - V4L2 / libcamera
      - power / thermal
      - Surface SSAM

## Technical precedent

NDISWrapper is the key historical precedent. It implemented Windows kernel and NDIS APIs inside Linux so Windows network drivers could execute natively without CPU binary emulation.

References:

- NDISWrapper: https://ndiswrapper.sourceforge.net/wiki/index.php/Main_Page
- Windows driver types: https://learn.microsoft.com/en-us/windows-hardware/drivers/kernel/types-of-windows-drivers
- WDM versus WDF: https://learn.microsoft.com/en-us/windows-hardware/drivers/wdf/differences-between-wdm-and-kmdf
- Building/loading WDF drivers: https://learn.microsoft.com/en-us/windows-hardware/drivers/wdf/building-and-loading-a-kmdf-driver

The important lesson is that the hard part is the Windows ABI and device model, not x86 instruction execution.

## Compatibility scope

The runtime will be demand-driven from real Surface driver imports and observed behavior.

Initial layers:

1. PE/COFF parser and relocation.
2. Import/export resolution.
3. NT service-symbol namespace.
4. DriverEntry invocation.
5. Object and reference management.
6. WDM device objects and symbolic interfaces.
7. IRPs and I/O stacks.
8. Events, timers, DPCs and work items.
9. Memory pools, MDLs and mappings.
10. PnP and power state transitions.
11. PCI and ACPI resource translation.
12. DMA/IOMMU-safe mappings.
13. Interrupt handling.
14. Registry/configuration.
15. WMI contracts where a target actually requires them.
16. KMDF compatibility for drivers that depend on WDF.

We will not attempt to clone every Windows API up front. The import table of each target becomes the implementation backlog.

## Two implementation paths

GFYMS should remain hybrid:

    Windows driver reverse engineering
          |
          +--> protocol is understood
          |       |
          |       +--> native Linux driver
          |
          +--> proprietary/difficult behavior
                  |
                  +--> GFYMS NT/WDM/WDF runtime

That lets us unlock hardware quickly while still moving mature behavior into normal Linux subsystems over time.

## Whole Surface target

The reverse-engineering target is the complete Surface package, not only audio.

Inventory:

- bus and platform drivers
- function and filter drivers
- KMDF/WDF dependencies
- user-mode companions
- firmware
- INF configuration
- CAT/signature metadata
- registry/service configuration
- hardware IDs
- ACPI, PCI and USB relationships

Known Surface Pro 7 corpus examples include:

- IntcAudioBus.sys
- IntcDMic.sys
- IntcSST.sys
- IntelSSTPreprocStreamer.dll
- IntelAudioDll_x64.dll
- IntelAudioService.exe

Those files are research inputs. The public build should not automatically redistribute proprietary binaries.

## Local-first reverse engineering

Use the Windows PC for the expensive analysis:

    Surface MSI
       |
       +--> MSI/INF extraction
       +--> PE inventory
       +--> hashes/signatures
       +--> hardware IDs
       +--> Ghidra static analysis
       +--> WinDbg / ETW / PnP / registry observations
       |
       v
    driver contract manifest
       |
       +--> imported NT/WDF symbols
       +--> device IDs
       +--> IOCTLs
       +--> callbacks
       +--> resources
       +--> firmware/protocol clues
       |
       +--> native Linux implementation plan
       +--> GFYMS NT/WDM/WDF ABI requirements

The GitHub repository receives derived manifests, protocol notes, tests and implementation source rather than automatically receiving the vendor payloads.

## Azure Linux

Azure Linux is useful, but not because it hides a Surface `.sys` stack.

Microsoft describes Azure Linux as a Microsoft-maintained open-source Linux distribution with an Azure-optimized kernel. Azure Linux 4 is currently in development/preview, while the documented 4.0 kernel baseline is 6.18 LTS.

Useful material to mine:

- Microsoft's kernel patch history;
- the CBL-Mariner/Azure Linux kernel source and MSFT-Merge history;
- kernel configuration choices;
- security/hardening changes;
- package/build provenance;
- reproducible build and supply-chain practices.

The official sources checked did not reveal a Microsoft-owned Azure Linux Surface driver layer. Surface support still comes from upstream Linux and the Linux-Surface project.

For GFYMS, Azure Linux should be treated as a donor/reference source for Linux engineering, not as an automatic binary-driver source.

References:

- Azure Linux overview: https://learn.microsoft.com/en-us/azure/azure-linux/azure-linux-overview
- Azure Linux repository: https://github.com/microsoft/azurelinux
- CBL-Mariner Linux kernel: https://github.com/microsoft/CBL-Mariner-Linux-Kernel
- Azure Linux package repositories: https://learn.microsoft.com/en-us/azure/azure-linux/package-repositories
- Linux Surface: https://github.com/linux-surface/linux-surface

Microsoft's Azure Linux documentation also makes clear that its supported scope is Azure workloads; we are borrowing its open-source engineering, not its product support guarantees.

## Qualification

A Windows driver is not supported merely because its entry point returns success.

Promotion requires evidence that:

1. the image loads and relocates;
2. imports resolve;
3. DriverEntry succeeds;
4. device/PnP initialization succeeds;
5. resources and DMA are safe;
6. I/O requests complete;
7. interrupt/DPC paths behave;
8. suspend/resume survives;
9. removal/unload is clean;
10. real Surface Pro 7 hardware functionality works.

Until then, the driver remains a research target.

## Repository layout

    tools/gfyms-native-re/
        Windows-host reverse-engineering tooling

    kernel/gfyms-winkernel/
        Linux-side NT/WDM/WDF compatibility work

    kernel/
        native Surface Linux kernel work

    packages/
        Arch packaging of the resulting native components
