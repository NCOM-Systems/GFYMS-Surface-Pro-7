# GFYMS Surface Pro 7 ABI Contracts

This document converts the first real restored Surface Pro 7 driver corpus into an evidence-backed compatibility contract map.

These contracts are research and implementation-planning boundaries. They do not imply that GFYMS should load Microsoft Windows .sys binaries into the Linux kernel. Native GFYMS implementation remains Linux-native; Windows ABI compatibility work is an explicit compatibility/runtime layer.

## Corpus baseline

| Metric | Observed |
|---|---:|
| Total files | 2,582 |
| PE images | 371 |
| SYS images | 77 |
| DLL images | 265 |
| EXE images | 29 |
| INF files | 100 |
| Runtime configuration files | 4 |
| MSI packages | 1 |
| PE Git-LFS pointers remaining | 0 |
| PE analysis errors | 0 |
| MSI Directory rows | 363 |
| MSI -> PE medium-confidence joins | 240 |
| MSI -> PE exact joins | 0 |
| MSI payloads unmatched by current PE-only matcher | 2,227 |

The 2,227 unmatched MSI payloads are not equivalent to 2,227 broken relationships. The current matcher is PE-focused while the MSI payload table includes many non-PE files and extraction layouts can lose original logical-path identity.

## Contract model

A GFYMS ABI contract records the observed Windows provider/module, semantic API family, driver coverage, reference count, concrete symbols, and the implementation boundary where compatibility behavior belongs.

The contract is behavioral. It should not be implemented as a blind Linux syscall translation for every Windows API.

## Observed contract families

| Contract | Provider | Evidence from corpus |
|---|---|---|
| Unicode and string primitives | ntoskrnl.exe | RtlInitUnicodeString: 77; RtlCopyUnicodeString: 73 |
| Memory, pool, and MDL | ntoskrnl.exe | ExFreePoolWithTag: 67; ExAllocatePoolWithTag: 65 |
| Synchronization and waits | ntoskrnl.exe | KeInitializeEvent, KeSetEvent, KeWaitForSingleObject: 58 each |
| I/O request and device dispatch | ntoskrnl.exe | IRP, device-object, completion, cancellation, and work-item APIs observed |
| Plug and Play and device interfaces | ntoskrnl.exe | PnP notification and interface APIs observed |
| Power management | ntoskrnl.exe | Power-setting callback and power-request APIs observed |
| Registry and configuration | ntoskrnl.exe | Registry open/query/create/update APIs observed |
| WMI and ETW | ntoskrnl.exe | IoWMIRegistrationControl: 69; EtwRegister/Unregister: 55 each |
| Thread and worker lifecycle | ntoskrnl.exe | PsCreateSystemThread, PsTerminateSystemThread, KeDelayExecutionThread |
| Timing and NT version gates | ntoskrnl.exe / hal.dll | Timing, version, and DDI availability APIs observed |
| Diagnostics | ntoskrnl.exe | DbgPrintEx, KeBugCheckEx, persistent-state APIs observed |
| Security checks | ntoskrnl.exe | SeTokenIsAdmin observed |
| Compiler/runtime helpers | observed in kernel images | CRT/compiler helper imports remain a separate runtime boundary |
| WDF provider binding | wdfldr.sys | 57-driver WDF binding cluster |

## Unicode and string primitives

Observed symbols:

- RtlInitUnicodeString
- RtlCopyUnicodeString
- RtlFreeUnicodeString
- RtlCompareUnicodeString
- RtlEqualUnicodeString
- RtlUnicodeStringToInteger
- RtlAnsiCharToUnicodeChar
- RtlAnsiStringToUnicodeString
- RtlUnicodeStringToAnsiString
- RtlInitAnsiString
- RtlFreeAnsiString

Implementation boundary: preserve Windows string-structure layout, length semantics, termination rules, allocation ownership, and conversion behavior. These should be compatibility primitives, not ordinary Linux C-string wrappers.

## Memory, pool, and MDL primitives

Observed symbols:

- ExAllocatePoolWithTag
- ExFreePoolWithTag
- ExFreePool
- MmMapLockedPagesSpecifyCache
- MmAllocatePagesForMdlEx
- MmFreePagesFromMdl
- MmUnmapLockedPages
- MmUnmapIoSpace

Implementation boundary: model ownership, alignment, page/MDL state, and mapping semantics explicitly. Do not reduce an MDL to an arbitrary heap pointer.

## Synchronization and wait primitives

Observed symbols:

- KeInitializeEvent
- KeSetEvent
- KeWaitForSingleObject
- KeClearEvent
- KeInitializeSpinLock
- KeAcquireSpinLockRaiseToDpc
- KeReleaseSpinLock
- KeInitializeSemaphore
- KeReleaseSemaphore
- KeReadStateEvent
- KeResetEvent
- KeWaitForMultipleObjects

Implementation boundary: preserve dispatcher-object state transitions, timeout behavior, wait modes, and synchronization ordering. Linux primitives can implement the internals, but Windows-facing semantics must remain explicit.

## I/O request and device dispatch

Observed symbols:

- IofCallDriver
- IoGetDeviceObjectPointer
- IoBuildSynchronousFsdRequest
- IoBuildDeviceIoControlRequest
- IoAllocateIrp
- IoFreeIrp
- IoCancelIrp
- IofCompleteRequest
- IoAllocateWorkItem
- IoFreeWorkItem
- IoQueueWorkItem

Implementation boundary: represent IRPs and device objects as explicit compatibility objects. Do not map every Windows call directly to a Linux file descriptor.

## Plug and Play and device interfaces

Observed symbols:

- IoRegisterPlugPlayNotification
- IoUnregisterPlugPlayNotificationEx
- IoRegisterDeviceInterface
- IoSetDeviceInterfaceState
- IoSetDeviceInterfacePropertyData

Implementation boundary: connect this contract to the GFYMS hardware graph and udev/device-model integration. INF hardware IDs and service bindings should become testable inputs to the same model.

## Power

Observed symbols:

- PoRegisterPowerSettingCallback
- PoUnregisterPowerSettingCallback
- PoRequestPowerIrp

Implementation boundary: translate Windows power-setting and request semantics onto the Linux power-management model without exposing Linux internals as Windows objects.

## Registry and configuration

Observed symbols:

- ZwOpenKey
- ZwQueryValueKey
- ZwSetValueKey
- ZwCreateKey
- ZwEnumerateKey
- RtlWriteRegistryValue

Implementation boundary: use a compatibility configuration store with deterministic tests. Do not depend on undocumented Windows registry internals.

## WMI and ETW

Observed symbols:

- IoWMIRegistrationControl
- EtwRegister
- EtwUnregister
- EtwWriteTransfer

Implementation boundary: keep telemetry plumbing separate from functional hardware paths. Reproduce the lifecycle and event behavior needed by the compatibility target rather than recreating Windows telemetry wholesale.

## Thread and worker lifecycle

Observed symbols:

- PsCreateSystemThread
- PsTerminateSystemThread
- KeDelayExecutionThread

Implementation boundary: model lifecycle, cancellation, wake-up, and shutdown semantics. Host Linux worker threads remain implementation details.

## Timing and NT version gates

Observed symbols:

- KeQueryPerformanceCounter
- KeStallExecutionProcessor
- RtlGetVersion
- RtlIsNtDdiVersionAvailable
- NtBuildNumber

Implementation boundary: make clock source, monotonicity, version reporting, and feature-gate semantics explicit.

## Diagnostics

Observed symbols:

- DbgPrintEx
- KeBugCheckEx
- KeCapturePersistentThreadState

Implementation boundary: map these into structured GFYMS diagnostics and crash reporting. A Windows-style bugcheck path must not blindly terminate the Linux host.

## Security checks

Observed symbol:

- SeTokenIsAdmin

Implementation boundary: model the permission decision required by the compatibility API while retaining the host Linux security model.

## Compiler and runtime helpers

Observed symbols include:

- _vsnwprintf
- _vsnprintf
- strncpy_s
- strncmp
- strcmp
- memcpy_s
- _purecall
- __C_specific_handler

These are not Windows kernel service APIs. They belong at the compiler/CRT/runtime compatibility boundary and should not be mixed into the semantic kernel ABI contract.

## WDF provider binding

Observed symbols:

- wdfldr.sys!WdfVersionBind
- wdfldr.sys!WdfVersionBindClass
- wdfldr.sys!WdfVersionUnbindClass
- wdfldr.sys!WdfVersionUnbind
- wdfldr.sys!WdfLdrQueryInterface

The corpus showed 57 drivers using the primary WDF binding calls.

Implementation boundary: WDF must be a distinct provider-level subsystem covering version metadata, bind negotiation, framework-object identity, driver initialization/teardown, queues/requests, callbacks, synchronization, and failure paths.

The WDF layer should not be reduced to exported function stubs. Driver behavior can depend on framework object and lifecycle semantics.

## Other observed kernel ABI

Imports that do not yet fit a named contract remain visible in the ABI map and backlog.

For each one, determine whether it is a real kernel service, a version-specific symbol, a compiler/runtime helper, a diagnostic path, or an artifact of static import metadata before adding implementation work.

## Driver-family mapping

The first corpus shortlist is concentrated around:

| Family | Representative binaries | ABI significance |
|---|---|---|
| Intel display audio | IntcDAud.sys | Multiple versioned copies expose shared behavior across package revisions |
| Intel audio / SST | IntcDMic.sys, IntcBTAu.sys, IntcSDW.sys, IntcSST.sys | Dense NT + WDF interaction cluster |
| Realtek storage/card-reader | RtsUer.sys | Distinct non-Intel driver path |
| Intel graphics | igdkmdn64.sys | Graphics kernel path requiring its own analysis boundary |

Repeated copies of the same filename should be deduplicated by SHA-256 before treating them as separate implementation targets.

## Implementation backlog

### Contract extraction

Preserve the complete import frequency census, contract IDs, driver coverage, delay-import state, ambiguous imports, and unresolved symbols.

### Contract test harness

Each contract should define Windows-facing structure layout, ownership, success/failure behavior, lifecycle rules, concurrency assumptions, deterministic unit tests, and differential tests where static evidence is insufficient.

### WDF boundary

Build WDF as a separate provider with explicit bind negotiation, lifecycle, framework-object, queue/request, and failure-path tests.

### Driver-family analysis

Use the 15-driver shortlist as the first reverse-engineering batch, consolidating exact duplicate binaries first.

### INF integration

Join ABI contracts to service names, service binaries, hardware IDs, install sections, Include directives, and driver-family metadata. The goal is to turn "driver imports X" into "this hardware-bound driver family requires contract X."

### MSI integration

Do not treat the current 240 medium-confidence joins as authoritative path identity. Improve MSI-to-extracted provenance using component/file/package identity before using MSI relationships to drive execution decisions.

## Current engineering boundary

The output of this phase is a contract map, not a compatibility implementation.

The next implementation unit should be one small, testable contract family plus one representative driver family, with behavior proven by tests before additional Windows APIs are added.

The Linux GFYMS kernel remains native Linux. Microsoft driver binaries remain research inputs; they are not copied into the Linux kernel as-is.
