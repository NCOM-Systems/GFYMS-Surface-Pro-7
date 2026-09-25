# GFYMS .NET Runtime Strategy

GFYMS treats managed Windows applications as a user-mode compatibility problem separate from the NT/WDM/WDF kernel-driver project.

## Runtime tiers

### Native .NET 10

Use Microsoft's cross-platform .NET runtime for portable managed applications. Current Arch Linux Extra packages provide dotnet-runtime 10.x.

This is the preferred path for applications targeting modern .NET and using cross-platform APIs.

### Legacy .NET Framework

Use Mono for applications targeting the old .NET Framework family when their API usage is sufficiently portable.

The Surface Pro 7 corpus already demonstrates this requirement: three IntelAudioService configurations target .NET Framework 4.6.1.

### Windows-specific managed applications

A managed application can still depend on Windows-only APIs such as user32/kernel32, WinRT, COM, WPF or Windows-specific native libraries.

Modern .NET does not magically translate those APIs to Linux. Microsoft explicitly documents those platform dependencies.

For this class, GFYMS keeps a Windows API compatibility fallback based on Wine + Wine Mono while the native Linux-compatible API surface is developed.

### Native Win32 applications

Non-managed PE applications continue through the normal Windows user-mode compatibility path.

## Surface evidence

The complete extracted SurfaceUpdate tree contains:

- IntelAudioService.exe.config targeting .NET Framework 4.6.1 in three repeated audio driver payloads.
- OneApp.IGCC.WinService.exe.config targeting .NET Framework 4.7.2.
- The Intel graphics service configuration also contains WCF named-pipe service endpoints.

This means the managed runtime belongs in GFYMS as an actual compatibility component, not merely as a generic desktop package.

## MSI handling

MSI is a Windows Installer package format, not a .NET runtime.

GFYMS should:

1. Parse MSI tables and extract its payload metadata.
2. Determine whether an installed EXE/DLL is managed and which runtime it targets.
3. Route a portable managed payload to native .NET.
4. Route legacy .NET Framework payloads to Mono when possible.
5. Route Windows-specific payloads/custom actions to the Windows API compatibility layer.

The native Linux msitools package is useful for inspecting/building MSI databases. It is not a drop-in replacement for the Windows Installer service.

## Runtime selection

The intended GFYMS user command is:

    gfyms-windows program.exe

The selector should prefer:

    modern managed + runtimeconfig.json -> dotnet
    legacy .NET Framework config      -> mono
    managed but Windows-only API      -> Wine + Wine Mono
    native Win32                      -> Wine

Explicit test overrides remain available so individual Surface services can be investigated.

## Arch packages

The GFYMS ISO should include:

- dotnet-runtime
- mono
- msitools
- wine
- wine-mono

The current Wine packages are a compatibility fallback, not the definition of the long-term GFYMS architecture.

## References

- https://learn.microsoft.com/en-us/dotnet/core/porting/framework-overview
- https://learn.microsoft.com/en-us/dotnet/core/install/linux
- https://github.com/mono/mono
- https://archlinux.org/packages/extra/x86_64/dotnet-runtime/
- https://archlinux.org/packages/extra/x86_64/mono/
- https://archlinux.org/packages/extra/x86_64/msitools/
