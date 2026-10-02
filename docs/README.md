# GFYMS documentation

The main [GFYMS README](../README.md) is the public map. This page is the deeper index: choose the document by the question you need answered.

## Start here

| If you want to… | Read |
|---|---|
| Understand the project, feature status, compatibility stack, and history | [Main README](../README.md) |
| Build the ISO locally or understand release artifacts | [ISO local build](./GFYMS-ISO-LOCAL-BUILD.md) · [Release plan](./GFYMS-RELEASE-PLAN.md) · [Build stack](./GFYMS-BUILD-STACK.md) |
| Understand what is actually supported on Surface Pro 7 | [Hardware contract](./GFYMS-HARDWARE-CONTRACT.md) · [Full port matrix](./GFYMS-FULL-SURFACE-PORT-MATRIX.md) |
| Inspect current project history and future work | [Shared timeline](./gfyms-timeline.json) |
| Use or review GFYMS Center | [Center guide](./GFYMS-CENTER.md) · [Pen Center](./GFYMS-PEN-CENTER.md) · [Pen latency plan](./GFYMS-PEN-LATENCY-PLAN.md) · [KDE integration](./GFYMS-KDE-PLASMA-INTEGRATION.md) |
| Understand WinRunner and driver boundaries | [Native Windows runtime](./GFYMS-NATIVE-WINDOWS-RUNTIME.md) · [ABI contracts](./GFYMS-ABI-CONTRACTS.md) · [WDM/IRP contract](./GFYMS-WDM-IRP-CONTRACT.md) · [WinKIT notes](./WINKIT-IMPLEMENTED.md) |
| Understand Android and APK support | [Native Android subsystem](./GFYMS-NATIVE-ANDROID.md) |
| Understand cameras, Hello, audio, and Surface hardware | [Port matrix](./GFYMS-FULL-SURFACE-PORT-MATRIX.md) · [Hello stack](./GFYMS-HELLO.md) · [Build stack](./GFYMS-BUILD-STACK.md) |
| Understand Find My support | [GFYMS Find My Bridge](./GFYMS-FIND-MY.md) · [OpenHaystack upstream](https://github.com/seemoo-lab/openhaystack) · [Apple Find My](https://www.apple.com/icloud/find-my/) |
| Stage or inspect Microsoft payloads legally | [Legal boundary](./LEGAL-AND-DISTRIBUTION.md) · [MS API Clone](./MS-API-CLONE.md) · [Integration plan](./MS-API-CLONE-INTEGRATION.md) · [Runtime manifest](../packages/gfyms-surface/runtime/README.md) |
| Use recovery, updates, or the private cloud reference | [Recovery tool](../packages/gfyms-surface/recovery/gfyms-recovery.py) · [Nextcloud reference](../cloud/nextcloud/README.md) · [Center guide](./GFYMS-CENTER.md) |
| Review the VM test report and asset gaps | [R0.01DEV audit](./R0.01DEV-VM-ASSET-AUDIT.md) · [Original test report](../RANTS/R0.01DEV/R0.01DEV.md) |

## Engineering references

- [`.manus` project rules](../.manus)
- [Architecture diagram](./diagrams/gfyms-architecture.png) · [source](./diagrams/gfyms-architecture.mmd)
- [Recovery diagram](./diagrams/gfyms-recovery.png) · [source](./diagrams/gfyms-recovery.mmd)
- [`.NET runtime strategy](./GFYMS-DOTNET-RUNTIME.md)
- [Manual Arch patcher](./GFYMS-USER-PATCHER.md)
- [Development requirements](../RANTS/R0.01DEV/R0.01DEV.md)

## Status language

- **Implemented** means source code, packaging, or documentation exists in this repository.
- **Experimental** means the boundary exists but needs controlled tests or real hardware evidence.
- **Planned** means the design is recorded but the feature is not in the ISO.
- **Qualified** means the behavior has passed the relevant Surface Pro 7 hardware test; a VM build alone is not qualification.

If a document and the main README disagree, update the source document and the shared timeline first, then update the README summary. Do not turn a research note into a support claim without evidence.
