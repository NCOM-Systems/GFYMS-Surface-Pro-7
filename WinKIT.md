# WinKIT — implementation baseline

WinKIT is GFYMS's literate Windows orchestration layer. The implementation in this repository is derived from the supplied WinKIT 0.1.0 blueprint, but only contracts that can be enforced by the actual implementation are activated here.

## Implemented boundaries

- Windows Installer inspection uses documented msi.dll APIs and a read-only database handle.
- MSI mutation is delegated to msiexec.exe and requires an explicit --apply.
- Windows trust verification uses WinVerifyTrust; the raw status is retained.
- .NET runtime inventory uses an explicit dotnet host path and preserves unparsed output.
- .NET runtime installers use only the documented /install /quiet /norestart adapter.
- Driver packages require an INF, catalog, manifest hash evidence, SignTool kernel-policy verification, and manifest hardware IDs that actually occur in the INF.
- WDK compilation is delegated to an already installed Visual Studio/WDK/EWDK environment.
- Unknown EXEs are not a supported runner kind.
- Linux support in this layer is limited to userspace orchestration; no Windows .sys loader or fabricated Linux kernel driver is implemented.

## Security invariants

1. Hash evidence is checked before mutation.
2. Windows-only APIs hard-stop on non-Windows.
3. Executable paths passed to the process runner are absolute local files.
4. The runner never invokes a shell.
5. Manifest paths are confined to the manifest root.
6. MSI inspection accepts only a single SELECT statement and uses a read-only database.
7. MSI reboot outcomes are preserved rather than silently forcing restart.
8. Driver signing is verification-only; WinKIT never creates or exports a signing key.
9. Unknown EXEs fail closed because file extension alone does not prove installer semantics.
10. Vendor binaries are inputs/evidence, not redistributable GFYMS source.

## Evidence model

Artifact hash -> Windows trust/signature evidence -> static inspection -> manifest policy -> execution -> post-execution verification.

The repository's ABI Map v2 remains the analysis/evidence layer. WinKIT is the controlled execution/orchestration layer.

## Source files

- winkit/core.py
- winkit/wintrust.py
- winkit/msi.py
- winkit/dotnet.py
- winkit/drivers.py
- winkit/runner.py
- winkit/cli.py
- winkit.sample.json
- scripts/build_wdk.ps1
- scripts/verify_driver_package.ps1
- tests/test_winkit.py

This document deliberately does not claim Microsoft ownership or authorship of the Python code. Microsoft headers and documentation remain the canonical source for native declarations and semantics.
