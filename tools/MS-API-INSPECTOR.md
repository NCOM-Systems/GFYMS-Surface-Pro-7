# GFYMS MS API inspector

`gfyms-api-inspect.py` is the Linux-safe first step of the MS API Clone implementation. It is **read-only**: it hashes and classifies staged artifacts and parses .NET metadata, but never installs, launches, modifies, or claims Authenticode trust.

## Usage

```bash
python3 tools/gfyms-api-inspect.py \
  /staging/Surface/app.runtimeconfig.json \
  --staging-root /staging/Surface \
  --output /staging/evidence/app-runtimeconfig
```

Outputs:

- `manifest.json` — schema version, path provenance, SHA-256/SHA-512, classification, PE metadata, .NET metadata, and explicit trust/execution boundaries.
- `classification.json` — compact classification and parsed metadata.

## Supported evidence

- OLE/MSI package candidate detection by compound-file magic.
- PE/COFF architecture, optional-header kind, section count, and entry RVA.
- `.runtimeconfig.json` framework, version, roll-forward, and configuration properties.
- `.deps.json` runtime target and library/target inventory.
- `.sys`, `.dll`, and `.exe` PE role classification.
- Staging-root containment enforcement.

## Deliberate non-goals

This tool does not implement `msiexec`, `msi.dll`, custom-action execution, registry inventory, UAC, reboot behavior, or Authenticode/`WinVerifyTrust`. Those belong in a separate Windows adapter and must be validated on Windows. See [`docs/MS-API-CLONE.md`](../docs/MS-API-CLONE.md) and [`docs/MS-API-CLONE-INTEGRATION.md`](../docs/MS-API-CLONE-INTEGRATION.md).
