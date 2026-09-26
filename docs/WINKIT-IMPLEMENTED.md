# WinKIT implementation notes

WinKIT is now represented as real repository code rather than only a literate specification.

The first implementation intentionally excludes undocumented Microsoft internals, a generic EXE installer abstraction, automatic Windows-driver-to-Linux-driver conversion, signing-key creation, and security-policy bypasses.

The ABI Map v2 tools remain responsible for corpus analysis. WinKIT consumes reviewed artifacts and manifests and provides a separately gated Windows execution path.

## Review gates carried into implementation

| Gate | Implementation |
| --- | --- |
| Hash pinning | SHA-256 checked before mutation |
| Trust | WinVerifyTrust for MSI/.NET artifacts; SignTool /kp for driver catalogs |
| MSI inspection | MsiVerifyPackageW + read-only MsiOpenDatabaseW |
| MSI execution | msiexec.exe with argv-only execution and /quiet /norestart |
| .NET runtime | explicit dotnet host; official documented installer switches |
| Driver install | PnPUtil /add-driver INF /install, only with allowDriverInstall |
| WDK build | absolute MSBuild path, explicit configuration/platform |
| Hardware IDs | manifest IDs must be present in the actual INF |
| Unknown EXE | unsupported and therefore rejected |
| Linux driver boundary | no kernel module fabrication |

## Current known validation boundary

The portable regression tests cover hashing, path confinement, command execution, MSI SQL gating, INF hardware-ID evidence, manifest validation, and .NET inventory parsing.

The actual WinTrust/MSI/PnPUtil/WDK paths still require Windows-host validation against the installed SDK/WDK and disposable test hardware or VMs. No Linux test is treated as proof that those Windows APIs execute correctly.
