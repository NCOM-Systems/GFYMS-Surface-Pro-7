# GFYMS Recovery Assistant

`gfyms-recovery` is an evidence-first recovery assistant. It is designed to tell the user what was observed before any repair is attempted.

## Commands

```bash
gfyms-recovery diagnose --output /var/lib/gfyms/recovery/latest
gfyms-recovery backup --output /var/lib/gfyms/recovery/latest --path /etc/gfyms
gfyms-recovery plan \
  --diagnosis /var/lib/gfyms/recovery/latest/diagnosis.json \
  --output /var/lib/gfyms/recovery/latest
```

The current implementation does not silently modify packages, boot entries, initramfs, user data, or firmware. A future repair executor must require explicit confirmation, preserve the evidence bundle, and verify the repaired boot before declaring success.

The boot service collects evidence after a successful boot. A non-booting device needs the same tool running from a GFYMS recovery ISO/USB environment with the installed root mounted read/write only after a backup decision.
