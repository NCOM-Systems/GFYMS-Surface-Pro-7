# GFYMS MS API Clone — implementation integration

**Status:** implementation blueprint derived from `docs/MS-API-CLONE.md`
**Date:** 2026-09-28

## Executive decision

The attached MS API Clone specification is a strong design for **artifact inspection and Windows installer orchestration**. It is not the same subsystem as WinRunner.

GFYMS should keep two explicit layers:

```text
MS API Clone / package orchestration
  inspect MSI, PE, .NET metadata, signatures, hashes
  resolve manifests and runtime prerequisites
  create deterministic plans and journals
  execute only approved Windows-side installers

WinRunner / kernel compatibility
  parse and map .sys PE images
  resolve NT/WDM/WDF imports
  expose executive, memory, IRP, PnP, power and DMA contracts
  execute qualified driver code on the Linux host CPU
```

The first layer manages **packages and prerequisites**. The second manages **kernel driver behavior**. A `.NET` runtime installer, MSI, or arbitrary setup EXE must never be treated as a kernel driver merely because it contains PE files.

## What already exists in GFYMS

| Specification capability | Existing repository location | Status |
|---|---|---|
| MSI table/stream/file extraction | `tools/export_msi.py` | Existing research tool; exports all discovered tables, streams, files, hashes, and pymsi reports |
| MSI dependency package | `tools/requirements-msi.txt` | Existing |
| PE/driver inventory and import analysis | `tools/gfyms-native-re/` | Existing research tooling |
| PE32+ image parsing and relocation | `kernel/gfyms-winkernel/src/loader.rs` | Implemented and tested |
| NT executive handles/events | `kernel/gfyms-winkernel/src/executive.rs` | Implemented and tested |
| Memory/MDL model | `kernel/gfyms-winkernel/src/memory.rs` | Implemented and tested |
| WDM IRP/device dispatch | `kernel/gfyms-winkernel/src/wdm.rs` | Implemented and tested |
| MSI execution on Windows | None | Not implemented; must remain a Windows adapter |
| Authenticode/WinVerifyTrust | None | Not implemented; Windows-only adapter |
| .NET release metadata resolver | None | Next package-orchestration milestone |
| Signed immutable execution journal | Partial report output only | Needs a dedicated schema and writer |

## Correct implementation boundary

### Linux build environment

Linux can safely implement the read-only and planning portions:

1. SHA-256/SHA-512 hashing and provenance.
2. PE/COFF classification and import inventory.
3. MSI database inspection through `pymsi` or another read-only parser.
4. `.runtimeconfig.json` and `.deps.json` parsing.
5. Manifest validation and deterministic plan generation.
6. Package classification: MSI, MSP, PE/EXE, `.sys`, .NET app, unknown.
7. Evidence bundles and normalized reports.

Linux must **not** claim to reproduce:

- `msiexec.exe` or the Windows Installer engine;
- `msi.dll` custom-action semantics;
- `WinVerifyTrust` results;
- Windows registry product inventory;
- Windows UAC/elevation behavior;
- Windows reboot/session-manager behavior.

Those require a Windows execution adapter or a disposable Windows VM test target.

### WinRunner

WinRunner should consume **derived driver manifests**, not MSI installer semantics. A driver manifest should provide:

- PE hash and architecture;
- section/import/export inventory;
- driver entry RVA;
- imported NT/WDM/WDF symbols;
- INF service/device IDs;
- IOCTLs and callback candidates;
- ACPI/PCI/USB IDs;
- firmware references;
- observed PnP/power requirements;
- qualification status and hardware-test evidence.

The MSI/API clone can produce the package evidence that feeds this manifest, but it should not be linked into the kernel crate.

## Implementation sequence

### Package Orchestration Milestone A — read-only analyzer

Build on `tools/export_msi.py` rather than replacing it:

- add canonical staging-root enforcement;
- emit both SHA-256 and SHA-512;
- classify PE/MSI/MSP/.NET artifacts;
- parse `runtimeconfig.json` and `.deps.json` when present;
- report required tables explicitly, including absent tables;
- mark `CustomAction` rows as review findings;
- preserve raw pymsi output and produce a normalized digest;
- never execute an extracted file.

Acceptance: analyzer output is deterministic for the same input and contains evidence paths for every normalized fact.

### Package Orchestration Milestone B — manifest and plan

Add a versioned manifest format with:

- artifact ID, kind, absolute staged path;
- SHA-256/SHA-512;
- signer policy/evidence fields;
- MSI identity/context fields;
- .NET family/version/architecture requirements;
- allowed operations and public properties;
- explicit reboot policy;
- verification rule;
- evidence references.

Generate a plan digest before execution. Retries must reuse the pinned plan, not resolve a newer runtime silently.

### Windows Adapter Milestone C — execution

Implement separately from the Linux crate, preferably as a Windows-host tool or a Windows CI fixture:

- `MsiVerifyPackage` and read-only `MsiOpenDatabase` inspection;
- `MsiEnumProductsEx` inventory;
- absolute-path `msiexec.exe` execution;
- raw exit code and MSI reboot normalization;
- bounded handling of Windows Installer busy state (`1618`);
- post-install identity verification;
- `WinVerifyTrust` signer evidence;
- `.NET` runtime installation and `dotnet --list-runtimes` verification.

Unknown EXEs remain inspect-only/manual-review unless a version-specific profile has exact arguments, allowed exit codes, signer/hash policy, and post-install detector.

### WinRunner Milestone D — driver runtime

Continue independently:

1. NT pool and object namespace.
2. MDL pinning and DMA/IOMMU contracts.
3. PnP and power state machines.
4. Registry/configuration abstraction.
5. Interrupt/DPC/work-item primitives.
6. Import/export host namespace.
7. Test-only `DriverEntry` invocation boundary.
8. Virtual WDM test driver.
9. One non-hardware Surface platform target.
10. Hardware qualification before any automatic ISO inclusion.

## CI layout

CI should use separate jobs:

- `ms-api-static-analysis`: Linux, read-only artifact analysis, schema tests.
- `win-installer-adapter`: Windows runner or disposable Windows VM; signed fixture packages only.
- `winrunner-crate`: Linux Rust unit tests and ABI contract tests; no proprietary payload execution.
- `surface-hardware-qualification`: self-hosted Surface Pro 7 runner; never a normal release gate until stable and explicitly labeled.

The ISO build may include open-source analyzers, manifests, and WinRunner contracts. It must not silently redistribute proprietary Microsoft `.sys`, `.dll`, firmware, or installer payloads.

## Immediate next coding task

The highest-value next step is **Milestone A**, extending `tools/export_msi.py` into a deterministic `gfyms-api-inspect` command with:

```text
inspect <artifact> --output <evidence-dir> --staging-root <root>
```

It should produce:

```text
evidence/
  metadata/manifest.json
  metadata/classification.json
  metadata/runtime-requirements.json
  metadata/digest.json
  tables/*.json
  tables/*.csv
  reports/*
  files/*
```

That gives WinRunner a trustworthy upstream evidence source while avoiding the architectural mistake of placing Windows Installer behavior inside the Linux kernel compatibility layer.
