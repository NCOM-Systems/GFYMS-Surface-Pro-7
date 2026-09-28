# Surface runtime manifest

This directory defines the ISO-installed mechanism for **user-approved, hash-pinned staging** of Microsoft Surface payloads.

## Install flow

1. Obtain a version-specific payload URL and SHA-256 from an official Microsoft source or an authorized package channel.
2. Add an entry to `surface-runtime-manifest.json`:

```json
{
  "id": "surface-driver-package-2026-09",
  "kind": "surface-driver-bundle",
  "filename": "SurfaceDriverPackage.exe",
  "url": "https://official.example.microsoft/...",
  "sha256": "64-lowercase-hex-characters"
}
```

3. Review the plan:

```bash
gfyms-surface-runtime \
  --manifest /usr/share/gfyms/surface/surface-runtime-manifest.json \
  --destination /var/lib/gfyms/surface-runtime
```

4. Apply only after review:

```bash
gfyms-surface-runtime \
  --manifest /usr/share/gfyms/surface/surface-runtime-manifest.json \
  --destination /var/lib/gfyms/surface-runtime \
  --apply
```

The tool downloads over HTTPS, writes atomically, verifies SHA-256, and never executes the payload. A Windows adapter must separately verify Authenticode and execute an approved installer profile. A `.sys` payload must separately pass WinRunner qualification before it can be loaded.

The shipped manifest is intentionally empty. This prevents the public ISO from silently bundling or downloading proprietary Microsoft payloads without a concrete, version-specific source and hash.
