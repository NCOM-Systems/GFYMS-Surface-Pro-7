# GFYMS Surface Pro 7 build audit

Date: 2026-09-27

## Verified CI failure

The failing release workflow was not failing while building the ISO. The Arch container completed the package build, ArchISO build, release checks, and produced a 2.7 GiB ISO. The next step failed at:

```text
split: release-build/gfyms-surface-pro-7-0.1.0-preview.3-x86_64.iso.part-00: Permission denied
```

The container runs as root and writes to a bind-mounted checkout. The GitHub Actions runner then tries to create the split fragments as the unprivileged host user. The ISO itself was therefore valid, but the job could not continue to publish it.

## Applied fix

The release builder now accepts `OUTPUT_OWNER=uid:gid` and performs a final ownership handoff on the output directory after checksums are generated. Both callers pass the host uid and gid:

- `.github/workflows/build-gfyms-release.yml`
- `tools/build-gfyms-release-local.sh`

The workflow artifact now contains the numbered ISO fragments and the three assembly/checksum files instead of only the oversized raw ISO:

- `*.iso.part-*`
- `ISO-SHA256SUM`
- `ISO-PARTS-SHA256SUMS`
- `ISO-ASSEMBLY.txt`

The GitHub Release publication already excludes the raw `.iso` and uploads the fragments plus metadata.

## Validation performed

- Bash syntax checks passed for both release build scripts.
- Repository Python compilation passed.
- Repository regression suite passed: **8 tests passed**.
- Workflow YAML parsed successfully with PyYAML.
- `git diff --check` passed.
- Numeric uid:gid ownership handoff was verified in a temporary artifact directory.

The sandbox does not have Docker or a Docker socket, so a fresh Arch container build could not be executed locally. The previous GitHub run log provides direct evidence that the Arch build reached the ISO output and failed only at the host-side split step.

## Important implementation boundary

The repository contains 372 tracked Windows payload files under `extracted/`, but the release builder does not copy that research corpus into the ISO. This is consistent with the repository's own distribution policy: Microsoft `.sys`, `.dll`, `.exe`, MSI, and firmware files are not automatically redistributable, and Windows kernel drivers cannot be loaded as Linux kernel drivers.

The current ISO package list contains `linux-surface`, `iptsd`, `libcamera`, `v4l-utils`, and related native Linux components. It does **not** contain a `gfyms-ipu4` package, a native Surface camera service, or a completed IPU4/IPU4P implementation. The documented OV5693, OV8865, and OV7251 camera support remains a planned/hardware-qualification target, not something the current ISO can honestly guarantee.

## Next engineering gate

After the workflow fix is merged, the next release should be labeled as a native Linux foundation/preview unless the project adds and qualifies the missing Surface camera and hardware pieces. The correct sequence is:

1. Re-run the release workflow and verify fragment reassembly plus `sha256sum -c ISO-SHA256SUM`.
2. Boot-test the ISO in a VM for package installation, SDDM, Plasma, services, and rollback tooling.
3. Implement or integrate a lawful native IPU4/IPU4P Linux camera path, including sensor topology and required firmware handling.
4. Qualify IPTS, Type Cover, SAM/ISH, suspend/resume, cameras, audio, and firmware on a real Surface Pro 7.
5. Only then promote the image beyond an explicitly labeled preview.
