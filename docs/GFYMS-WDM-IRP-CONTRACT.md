# GFYMS WDM / IRP Contract

Microsoft documents that the Windows I/O manager routes IRPs through driver-supplied dispatch routines selected by major function code. Each driver in a layered stack receives its own I/O stack location, while the IRP status block carries completion status and request-dependent information.

The GFYMS model keeps those relationships explicit without loading Microsoft kernel binaries into Linux.

## Current Rust model

kernel/gfyms-winkernel/src/wdm.rs provides:

- DriverObject: typed dispatch table for supported IRP major functions.
- DeviceObject: process-local device identity, driver ownership, flags, and device-extension storage.
- Irp: explicit stack locations, current-stack cursor, I/O status block, and completion lifecycle.
- IoStackLocation: major/minor function codes, decoded request parameters, and control flags.
- IoStatusBlock: NTSTATUS plus request-dependent information.
- Completion routine registration and exactly-once completion transition.
- Explicit current/next stack access and copy/skip operations.

## Scope

This is a compatibility contract model, not a Windows PE loader and not a kernel module yet.

Native Rust synchronization and ownership implement the first test harness. Later Linux-kernel integration can replace internals while preserving the tested behavioral interface.

## Current major-function coverage

- IRP_MJ_CREATE
- IRP_MJ_CLOSE
- IRP_MJ_READ
- IRP_MJ_WRITE
- IRP_MJ_FLUSH_BUFFERS
- IRP_MJ_DEVICE_CONTROL
- IRP_MJ_INTERNAL_DEVICE_CONTROL
- IRP_MJ_POWER
- IRP_MJ_SYSTEM_CONTROL
- IRP_MJ_PNP

Unsupported codes remain explicit rather than silently mapping to a generic handler.

## Next boundary

The next layer is a device-stack manager:

1. Register device nodes.
2. Attach and detach driver/filter stacks.
3. Route IRPs to the selected device stack.
4. Preserve each driver's stack location.
5. Implement completion unwinding.
6. Connect PnP and Power minor functions to the hardware graph.

Only after this should Surface-specific PCI/ACPI translation and real driver-family experiments begin.
