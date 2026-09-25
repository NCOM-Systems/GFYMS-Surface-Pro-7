# GFYMS Native Reverse Engineering Kit

Windows-host tooling for turning the Surface Pro 7 Windows driver package into a machine-readable research corpus.

The kit is local-first. It does not automatically publish vendor SYS, DLL, EXE or firmware payloads.

## Collect the corpus

    Set-ExecutionPolicy -Scope Process Bypass

    .\\Collect-SurfaceDriverCorpus.ps1 `
      -DriverRoot 'C:\\GFYMS\\surface-drivers\\extracted' `
      -OutputRoot 'C:\\GFYMS\\surface-drivers\\research'

The collector records:

- SYS/DLL/EXE inventory
- SHA-256 hashes
- Authenticode status
- INF relationships and key directives
- installed PnP driver metadata
- kernel-service metadata

## Extract imports

    .\\Extract-DriverImports.ps1 `
      -DriverRoot 'C:\\GFYMS\\surface-drivers\\extracted' `
      -OutputRoot 'C:\\GFYMS\\surface-drivers\\research\\imports'

The importer prefers LLVM tools when present and falls back to Visual Studio or Windows SDK dumpbin. Import inventories become the implementation backlog for the GFYMS NT/WDM/WDF compatibility layer.

## Run Ghidra

    .\\Run-GhidraInventory.ps1 `
      -DriverRoot 'C:\\GFYMS\\surface-drivers\\extracted' `
      -GhidraHeadless 'C:\\Program Files\\Ghidra\\support\\analyzeHeadless.bat' `
      -OutputRoot 'C:\\GFYMS\\surface-drivers\\research\\ghidra'

## What belongs in Git

Prefer:

- manifest data
- hardware/device IDs
- hashes
- imported-symbol inventories
- protocol observations
- tests
- native Linux implementations
- GFYMS compatibility-layer source

Do not automatically commit the original vendor binaries.

## Next stage

The generated manifest and import inventory become the input backlog for:

    kernel/gfyms-winkernel/

The implementation should follow documented Windows contracts and observed driver behavior.

## Build the complete ABI map

After the MSI has been extracted and Git-LFS binaries are restored, run:

    .\\Build-SurfaceAbiMap.ps1 -DriverRoot 'C:\\GFYMS\\surface-drivers\\extracted' -OutputRoot 'C:\\GFYMS\\surface-drivers\\research\\abi-map'

The output contains every SYS/DLL/EXE PE image, machine/architecture information, CLR/.NET detection, imported modules and symbols, exported symbols, INF hardware IDs and service bindings, .NET runtime configuration, duplicate-binary relationships, an initial dependency graph, and the NT/WDF import backlog.

The map reports unresolved Git-LFS pointers rather than treating pointer text as PE files.

## Important corpus note

The public Git repository stores large binary corpus objects through Git LFS. A checkout without restored LFS objects will therefore show small pointer files for many SYS/DLL/EXE/CAT/BIN objects.

Restore the LFS objects on the Windows analysis machine before generating the real import-level ABI map.



## ABI Map v2 workflow

Run the mapper against the extracted corpus root so MSI table exports remain visible:

```powershell
python tools/gfyms-native-re/build_abi_map.py C:\src\GFYMS-Surface-Pro-7\extracted --schema v2 --output C:\GFYMS\research\abi-map\abi-map.json --markdown C:\GFYMS\research\abi-map\abi-map.md
python tools/gfyms-native-re/render_backlog.py C:\GFYMS\research\abi-map\abi-map.json --output-csv C:\GFYMS\research\abi-map\backlog.csv --shortlist C:\GFYMS\research\abi-map\ghidra-shortlist.json
```

v2 emits explicit delay-imports, host ABI nodes for missing Windows modules, WDF evidence, structured INF data, MSI Directory/Component/File joins, and runtime requirements. The driver backlog is analysis output; it does not imply that vendor `.sys` files are executed by GFYMS.
