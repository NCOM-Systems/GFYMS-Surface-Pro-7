# GFYMS Arch Patcher

Planned user-facing update utility for existing Arch/Arch-based Surface Pro 7 systems.

## Design

`gfyms-patch` should:

1. Detect the exact Surface Pro 7 hardware profile.
2. Check Arch compatibility and current kernel state.
3. Create a boot/configuration snapshot.
4. Verify the GFYMS repository key and package metadata.
5. Show the planned package/kernel changes.
6. Apply packages and configuration.
7. Run post-install diagnostics.
8. Generate a rollback/support report.

Never silently replace a boot-critical configuration and never silently flash firmware.

## Example interface

```bash
gfyms-patch check
gfyms-patch plan
gfyms-patch apply
gfyms-patch verify
gfyms-patch rollback
gfyms-patch report
```

The implementation should eventually be a signed package distributed from the same GFYMS repository used by the official ISO.