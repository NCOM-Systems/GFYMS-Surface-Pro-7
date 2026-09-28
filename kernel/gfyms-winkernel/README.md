# GFYMS WinRunner kernel compatibility layer

This crate is the first executable implementation milestone for WinRunner: a Linux-side NT/WDM/WDF compatibility environment intended to execute selected x86_64 Windows driver machine code directly on the host CPU, without CPU instruction emulation.

## Implemented in this milestone

- `loader` — validates AMD64 PE32+ images, maps headers/sections into a bounded simulated address space, applies supported `DIR64` base relocations, resolves import descriptors through an explicit resolver, records the image entry point, and seals the image read-only.
- `executive` — process-local typed handles, named object namespaces, typed references, duplicate/close services, event objects, signal/reset, and wait services.
- `memory` — aligned zeroed allocations, tagged `ExAllocatePool2`/`ExFreePoolWithTag`-style pool semantics, bounds-checked reads/writes, protection changes, release, and MDL-style lock tracking.
- `wdm` — typed driver/device objects, IRP stack locations, dispatch routines, status blocks, completion routines, and copy/skip stack operations.
- `sync`, `unicode`, `status` — tested NT synchronization, counted UTF-16, and NTSTATUS primitives.

## Safety boundary

This milestone **does not invoke `DriverEntry` or execute arbitrary vendor code**. The PE loader returns an entry-point address as metadata only. It does not create a callable function pointer, map executable host memory, access PCI/ACPI hardware, or load the Microsoft Surface corpus into the Linux kernel.

That boundary is deliberate. Before real `.sys` execution, WinRunner still needs an audited NT executive ABI, WDM lifecycle, PnP/power, object manager, pool/MDL/DMA, interrupt/DPC, registry, KMDF, and hardware-resource translation implementation. A target driver must pass load, import, PnP, I/O, interrupt, suspend/resume, unload, and physical Surface Pro 7 qualification before promotion.

## Verification

Run:

```bash
cargo test --manifest-path kernel/gfyms-winkernel/Cargo.toml
```

The current milestone has 29 passing unit tests covering PE parsing/mapping, memory protection, tagged pool and MDL state, named executive objects/events, synchronization, Unicode, WDM dispatch, IRP completion, and status behavior.

## Next implementation boundary

1. Add a real object-manager namespace and reference-counted executive objects.
2. Add pool allocation, MDL pinning, DMA-map contracts, and strict teardown.
3. Add PE import/export host namespaces and a test-only `DriverEntry` invocation boundary.
4. Add PnP/power state machines and device-stack attach/detach with completion unwinding.
5. Add KMDF object wrappers based on the ABI inventory.
6. Build a virtual test driver before attempting a simple Surface ACPI/SAM target.
