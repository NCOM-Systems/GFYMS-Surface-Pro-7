# GFYMS Surface Pro 7

Utilities for inspecting and extracting the Microsoft Surface Pro 7 Windows 11 driver MSI.

## pymsi integration

This repository uses [nightlark/pymsi](https://github.com/nightlark/pymsi) for MSI parsing and extraction.

pymsi also provides an [MSI Viewer and Extractor](https://pymsi.readthedocs.io/en/latest/msi_viewer.html) that processes the selected MSI entirely in the browser. The local automation in this repository uses the pymsi CLI instead so the MSI never needs to be uploaded to the viewer.

## Extract the Surface Pro 7 MSI

The PowerShell helper expects this MSI by default:

```text
C:\Users\Offic\Downloads\SurfacePro7_Win11_22621_25.090.3489.0.msi
```

Run from the repository root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\extract_surfacepro7_msi.ps1
```

The script:

1. Creates an isolated Python virtual environment for pymsi.
2. Installs the current `main` branch of `nightlark/pymsi`.
3. Validates the MSI with `pymsi test`.
4. Extracts the MSI contents with `pymsi extract`.
5. Packages the extracted files as a ZIP under `artifacts\`.
6. Writes a SHA-256 manifest for the source MSI and generated ZIP.
7. Commits and pushes the ZIP and manifest to this GitHub repository.

The raw MSI is never copied into the repository.

## Large ZIP files

GitHub blocks regular Git objects larger than 100 MiB. The helper automatically uses Git LFS for the generated ZIP when it is at or above 90 MiB, provided Git LFS is installed. GitHub documents Git LFS as the supported mechanism for large binary files.

## Output

Expected output names:

```text
artifacts\SurfacePro7_Win11_22621_25.090.3489.0-extracted.zip
artifacts\SurfacePro7_Win11_22621_25.090.3489.0-extracted.sha256.txt
```

The MSI itself remains outside the repository.
