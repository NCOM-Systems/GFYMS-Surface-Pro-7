# GFYMS legal and distribution boundary

GFYMS is a hardware-enablement project for the Microsoft Surface Pro 7. The project may inspect vendor packages, document hardware behavior, and create independently implemented Linux software. That does not automatically give the project a license to redistribute Microsoft's binaries.

## The important distinction

Owning a Surface Pro 7 gives the owner rights concerning the physical device. It does not, by itself, transfer Microsoft's copyright or license rights in Windows drivers, DLLs, EXEs, kernel drivers, firmware packages, or other copyrighted software.

U.S. copyright law contains specific limitations for software owners. 17 U.S.C. §117 permits certain copies/adaptations that are an essential step in using a program with a machine and certain archival copies. It does not create a blanket right to publish the program for everyone else.

17 U.S.C. §1201(f) also provides a specific interoperability reverse-engineering path for a lawfully obtained program, subject to its conditions. That is not a blanket permission to redistribute the original copyrighted program or to bypass unrelated protections.

For GFYMS, the practical rule is therefore:

**Research is not the same thing as redistribution.**  
**Hardware ownership is not the same thing as a software redistribution license.**

## Distribution classes

| Material | Git repository | GFYMS ISO/repository | Build-time acquisition |
|---|---|---|---|
| GFYMS-authored source | Yes | Yes | Yes |
| Linux kernel patches/config | Yes | Yes | Yes |
| Device IDs / ACPI IDs / hashes / metadata | Yes | Yes | Yes |
| Clean-room protocol notes and derived interfaces | Yes | Yes | Yes |
| Microsoft Windows .INF text copied from a vendor package | Treat as third-party; minimize | No unless clearly licensed | Prefer generated/derived metadata |
| Microsoft .SYS/.DLL/.EXE | Quarantine only; do not treat as redistributable | No by default | User/vendor acquisition only |
| Microsoft firmware payloads | No by default | No by default | Only where an applicable license and safe update path permit it |
| Open-source Linux firmware | Yes when its license permits | Yes | Yes |
| Third-party packages | Per their licenses | Per their licenses | Per their licenses |

The existing extracted directory is a **research corpus**, not a statement that every extracted file is distributable. It should be treated as a quarantine area for reverse engineering and provenance. Do not copy Windows binaries from that tree into a public GFYMS package or ISO merely because the machine owner can personally use them.

## Recommended acquisition model

1. The user obtains an official Surface driver/firmware package from Microsoft or another authorized source.
2. GFYMS verifies the expected package identity and SHA-256.
3. GFYMS extracts only the artifacts needed for the user's own machine.
4. Native Linux code consumes only the lawful/relevant firmware or metadata.
5. Windows kernel drivers are never loaded by Linux.
6. Windows user-space utilities may be offered to the optional .EXE runner only when their own license permits personal use and the user provides the software.
7. The GFYMS public repository contains the Linux implementation, metadata, hashes, build recipes, tests, and documentation rather than Microsoft's proprietary implementation.

## Windows Hello naming

The feature exposed by GFYMS should be named something such as **GFYMS Hello** or **Surface Face Unlock**. It can be described as a *Windows Hello-style* feature for Linux, but it should not imply that GFYMS contains Microsoft's Windows Hello implementation or is endorsed by Microsoft.

The Surface Pro 7 has a dedicated Windows Hello facial-recognition camera. GFYMS can use that hardware through a native Linux camera/authentication stack without shipping Windows Hello itself.

## Reverse engineering

Keep reverse engineering focused on interoperability, protocol behavior, hardware identification, and independently implemented Linux interfaces. Record the source package, version, device IDs, hashes, and observations so the work is reproducible without turning the repo into a dump of vendor software.

Before redistributing any extracted Microsoft file, check the license/terms that actually accompany that file or package. The fact that a file was downloadable from Microsoft does not by itself establish a public redistribution license.

## Not legal advice

This file is an engineering distribution policy, not legal advice. For a commercial release, large-scale redistribution, firmware redistribution, or a dispute about a specific Microsoft component, obtain advice from a qualified attorney familiar with software licensing and copyright.