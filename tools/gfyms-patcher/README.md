# GFYMS Arch Patcher

This release contains the first executable preview of the existing-Arch updater.

```bash
sudo ./gfyms-patch check
sudo ./gfyms-patch apply
```

The preview updates only the native GFYMS package from the configured pacman repository and runs `gfyms doctor`. It does not flash firmware, replace a bootloader, or install vendor Windows drivers.
