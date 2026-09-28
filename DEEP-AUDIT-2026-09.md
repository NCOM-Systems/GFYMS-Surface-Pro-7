# GFYMS Surface Pro 7 — deep engineering audit

**Date:** 2026-09-27
**Repository:** `NCOM-Systems/GFYMS-Surface-Pro-7`
**Audited revision:** the pushed `main` revision containing the release-artifact ownership fix
**Current release run observed:** [GitHub Actions run 36342310594](https://github.com/NCOM-Systems/GFYMS-Surface-Pro-7/actions/runs/36342310594)

## Executive conclusion

The project has a useful and unusually valuable research corpus, but the current tree is not yet an operating-system distribution that can honestly claim to ship Microsoft's Surface drivers. It is currently an ArchISO profile containing `linux-surface`, `iptsd`, common Linux camera/audio/sensor packages, GFYMS diagnostics, and a large Windows-driver research corpus kept outside the ISO profile.

The most important correction is conceptual: the extracted `.sys` files are **Windows PE/WDM/WDF binaries**, not Linux kernel modules. They can provide hardware IDs, register/protocol clues, firmware/calibration payload candidates, and reference behavior. They cannot be placed in `/usr/lib/modules` and loaded by Linux. The repository's own restored-binary analysis found **371 PE images, 77 `.sys` files, 100 INF files, 265 DLLs, 29 EXEs, and four runtime configurations**. The binaries import `ntoskrnl.exe` in 77 images and `wdfldr.sys` in 57, which is direct evidence of Windows kernel/framework dependencies.

The project should therefore ship three clearly separated things:

1. **A native Linux Surface layer** built on the Linux Surface kernel/userspace stack and new Linux drivers where necessary.
2. **A research/evidence corpus** that is not silently treated as redistributable Linux driver payload.
3. **An optional Windows-application compatibility layer** based on Wine/native .NET where it is useful; this is unrelated to loading Windows kernel drivers.

## What the restored corpus actually proves

The repository was initially checked out with Git-LFS pointer files because Git LFS was not installed in the sandbox. After restoring the 518 LFS objects, the corpus became analyzable. The high-signal inventory contains:

| Area | Concrete evidence in `extracted/files/ProgramFiles64Folder/SurfaceUpdate` | Correct Linux interpretation |
|---|---|---|
| Cameras | `camera/iacamera64.sys`, `camerasensor5693/ov5693.sys`, `ov8865/ov8865.sys`, `ov7251/ov7251.sys`, sensor `pipeCfg.bin` files, IPU configuration/CPD files | Use as reverse-engineering/calibration/protocol evidence. Build a native IPU4/IPU4P kernel + libcamera path; do not load these Windows drivers. |
| Surface platform/SAM | `sam/SurfaceSAM.inf`, `SurfaceSAM_14.800.139.bin`, Surface integration, battery, buttons, HID, cover, backlight, power and ACPI packages | Map ACPI IDs, protocol messages, firmware versions and behavior to existing Linux Surface support. Firmware blobs need separate provenance and update policy. |
| ISH/sensors | `ishbus/ISH_BusDriver.sys`, `ishheci/ISH.sys`, sensor-related Surface drivers | Prefer Linux ISH/IIO support. Windows UMDF/WDM services are not portable modules. |
| Audio | Intel SST/DMIC/SDW/OED drivers, DSP firmware, topology XML, WoV files | First use Linux SOF/ALSA topology and `linux-firmware`; use corpus files only after license/provenance review and hardware validation. |
| Wi-Fi/Bluetooth | Intel Windows `Netwtw*.sys` and `ibtusb.sys` payloads | Use upstream `iwlwifi`, `btintel`/`btusb`, and `linux-firmware`. Do not ship Windows networking drivers. |
| Touch/Pen/Type Cover | `iaPreciseTouch.sys`, Surface touch/pen/cover integration and firmware-update packages | Implement through Linux HID/IPTS/SAM/I2C/USB paths; vendor firmware must never be flashed automatically. |
| Fingerprint/Hello | Surface fingerprint UMDF DLLs and WinUSB/WUDF service metadata | Treat as a protocol/research lead only. Investigate `libfprint`; do not claim Windows Hello support from the DLLs alone. |
| Firmware/update payloads | Surface UEFI, ME, PD, touch, dock and pen `.bin`/offer/payload files | Inventory and hash; do not include an automatic flasher in the installer. A wrong firmware update can brick a device or accessory. |

The ABI mapper produced no PE analysis errors after LFS restoration. Its most important result is not a list of “portable drivers”; it is the dependency boundary: Windows kernel APIs, WDF loader APIs, Windows setup APIs, ETW/WMI, and user-mode Windows DLLs dominate the corpus.

### Camera status is now a realistic native-Linux target

The current upstream research is much more promising than the repository's present package list suggests. The linux-surface IPU4 discussion documents a working Surface Pro 7 path based on an `ipu4-next`-derived kernel series, including OV8865 rear capture and OV5693 front capture. It also documents the hard parts: CSI-2 receiver timing, front-camera building-block selection, settle values, and remaining libcamera/PipeWire integration. The same discussion reports IR OV7251 probing problems on the tested unit. This should be treated as an experimental **kernel branch plus libcamera integration project**, not as “copy the Microsoft camera driver into the ISO.”

The practical camera roadmap is:

1. Bring the validated IPU4 patch series into a dedicated `linux-surface-ipu4` kernel package.
2. Add the exact Surface Pro 7 sensor tables, CSI-2 timing quirks and pipeline configuration under a clearly versioned source tree.
3. Test raw capture with `media-ctl`, `v4l2-ctl` and a repeatable cold-boot/stream-start matrix.
4. Add a libcamera pipeline/IPA path and only then integrate PipeWire/WirePlumber.
5. Keep the Windows CPD/pipe configuration files in the research package until provenance, redistribution rights and exact format are documented.

libcamera itself is an open userspace camera stack that depends on Linux kernel APIs/drivers already being present. Its documentation explicitly separates the open core from platform-specific pipeline code and optional IPA components; it does not make Windows `.sys` drivers loadable.

## Cloud-backed system and recovery storage

### The hard boundary

Do **not** put `/`, `/usr`, `/boot`, the EFI System Partition, the initramfs, or the active database/journal on a network filesystem. A remote mount cannot replace the local boot chain: it needs networking, credentials, a working kernel/initramfs, correct clocks and a reachable server before the operating system can use it. Network loss, captive portals, server maintenance, stale caches, or a corrupted remote cache would turn normal boot into recovery.

The useful design is “cloud-backed personal data and recovery,” not “cloud root disk.” Keep a small local encrypted system and use the remote service as a synchronized/cacheable data tier plus a versioned backup target.

### Recommended architecture

| Approach | Appropriate use | Tradeoffs | Cost | Setup complexity |
|---|---|---|---|---|
| **Recommended: Nextcloud sync + restic snapshots** | Nextcloud client for selected user folders; restic for `/home`, `/etc`, package manifests, boot metadata and recovery bundles | Local files remain usable offline; Nextcloud gives sharing/history UX; restic gives encrypted, deduplicated, verifiable point-in-time recovery. Requires two policies and enough local cache space. | Self-hosted server/NAS/VPS plus storage; software can be free | Medium |
| **Private object storage + rclone crypt + restic** | Encrypted bulk archive, media and off-device backups using S3-compatible storage, SFTP or a server | Less application UX than Nextcloud; rclone VFS is not a real disk and needs a cache. Good for low local storage if files are accessed selectively. | Storage/backend cost; rclone/restic are free | Medium-low |
| **Nextcloud/WebDAV mount as a “second system drive”** | Occasional documents or a non-critical shared directory | WebDAV requires connectivity; generic mounts have weaker filesystem semantics and poor behavior for databases/build trees. Official Nextcloud docs recommend the desktop sync client for normal synchronization. | Server/storage cost | Low initially, high when it breaks |
| **Remote root/system disk** | Not recommended for this device | Boot/network/key dependency, failure amplification, latency, and recovery complexity. It is not a OneDrive equivalent for `/usr` or `/boot`. | Highest operational risk | Very high |

Nextcloud's official documentation recommends its desktop sync client when files must be available offline and documents WebDAV as a remote access method. rclone's VFS documentation says file caching is needed for normal read/write semantics, that buffering can consume `--buffer-size` per open file, and that an interrupted upload may remain pending. That is exactly why rclone is suitable for a user-data/cache tier but not for a boot filesystem.

### Hands-free service design

Implement a `gfyms-cloud` optional package, disabled by default until configured. It should provide:

- A systemd **user** service for the Nextcloud client or an rclone mount, with an explicit local cache path and size limit.
- A systemd timer for restic snapshots with randomized delay, network-online gating, exponential retry and a clear “last successful backup” status.
- A second timer for `restic check` and a monthly restore test into a temporary directory.
- Separate credentials for sync and backup; use app passwords or repository passwords, never the user's main password in the ISO.
- A local encrypted key file protected by TPM2 only after a tested recovery-key path exists. The recovery key must be offline and not stored solely on the cloud mount.
- A read-only recovery bundle containing package manifests, kernel/initramfs versions, `crypttab`, fstab, boot entries, hardware diagnostics and the exact GFYMS release.
- Versioning/immutability on the backup destination where available, because a live sync service is not a defense against ransomware or accidental deletion.

The recovery workflow should be: boot GFYMS USB, unlock the local disk, bring up networking, retrieve a selected restic snapshot or local Nextcloud-synced recovery bundle, verify its checksum/signature, restore to a new local filesystem, and only then reinstall the bootloader/UKI. The cloud service must never be required to boot the USB recovery environment.

## Installer, boot TUI and Secure Boot

The current ISO profile has three boot modes: `uefi-x64.systemd-boot`, `uefi-x64.grub`, and `bios.syslinux.mbr`. That maximizes compatibility but does not equal Secure Boot support. The package profile also describes a workstation image, not an installer: there is no verified disk-partitioning, LUKS setup, rollback, boot-entry preservation, or signed-UKI installation path in the audited files.

### Proposed installer phases

1. **Preflight:** verify x86_64, UEFI mode, Surface Pro 7 identity, AC power, free disk space, network status, and whether Secure Boot is enabled. Make the user export a recovery report.
2. **Target selection:** enumerate only whole disks, show model/size/serial, require an exact typed confirmation, and refuse the current live USB.
3. **Storage:** default to GPT + EFI System Partition + LUKS2 + Btrfs subvolumes (`@`, `@home`, `@var`, `@snapshots`) with conservative mount options. Offer a simple ext4 path for users who do not want Btrfs.
4. **Install:** install a minimal base, the Surface kernel package, firmware, network, graphics, and recovery tools first. Install Plasma and optional Windows compatibility packages as selectable layers.
5. **Boot:** install a signed systemd-boot/UKI path, create a fallback entry, retain the previous entry where possible, and generate a rescue entry that does not depend on the cloud.
6. **Post-install:** enable only the services selected by the user, run `gfyms doctor`, save a machine-readable qualification report, and print the rollback/recovery instructions.

A TUI is appropriate here, but it should be a small, auditable front-end around tested shell/Python operations—not a giant installer that combines disk code, firmware flashing, cloud credentials and driver experimentation in one privileged process. Provide a `--dry-run`, `--json-report`, and `--non-interactive` mode for testing.

### Secure Boot path

Use a UKI-based path for the installed system. A UKI combines the UEFI stub, kernel, initramfs and embedded resources into one signed PE image, which gives a clear object to sign and verify. The ArchWiki documents `ukify`/`systemd-sbsign`, `sbctl`, automatic signing, and the requirement to manage firmware keys carefully. Preserve Microsoft and OEM keys unless the user explicitly chooses a different trust model; removing them can affect firmware updates or Windows boot.

The ISO and installed OS should be treated separately:

- **Installed OS:** generate and sign the UKI in the user's installation, with the private key never committed to GitHub or embedded in the ISO.
- **GFYMS USB:** either publish a separately signed boot path with a documented trust/enrollment process, or state clearly that Secure Boot must be disabled/enrolled for the recovery USB. Do not pretend an unsigned ArchISO is Secure Boot-capable.
- **CI:** verify signatures with `sbverify`/`sbctl verify`, hash the UKI and EFI binaries, and fail if a private key or signing secret appears in the workspace or artifact.
- **Updates:** use a pacman/mkinitcpio hook to rebuild and sign new UKIs; keep at least one previous signed UKI for rollback.

## Build and performance backlog

The current package file has 68 lines and includes a full Plasma desktop plus Wine, Wine Mono, Wine Gecko, Winetricks, Mono, .NET runtime, developer tools, multiple KDE utilities, and several diagnostic packages. That is a poor default for a memory-constrained Surface. Keep the hardware image small and offer `gfyms-desktop-extra` and `gfyms-windows-compat` as post-install groups.

### Highest-value changes

| Priority | Change | Why | Verification |
|---|---|---|---|
| P0 | Split package profiles into `base`, `surface`, `desktop`, `windows-compat`, `developer`, and `recovery` | Reduces ISO size, install time and idle memory; avoids forcing Wine/.NET onto every install | Build each profile; measure ISO size, install time and idle RSS |
| P0 | Add a real physical-SP7 qualification harness | VM success cannot prove IPTS, camera, SAM, ISH, Type Cover, suspend or firmware behavior | Publish `gfyms hardware-report.json` from a real device |
| P0 | Add LFS validation before corpus analysis | Prevents another false audit over pointer files | CI checks that every expected PE is not an LFS pointer before running `pefile` |
| P0 | Keep extracted corpus out of the ISO and out of automatic firmware actions | The corpus is multi-gigabyte and contains vendor components with separate redistribution/update risk | Assert ISO contents do not contain `extracted/` or Windows `.sys` payloads |
| P1 | Add IPU4 kernel package and camera test package | This is the real path to native SP7 cameras | Cold-boot, stream-start, front/rear/IR matrix; `media-ctl`, `v4l2-ctl`, libcamera logs |
| P1 | Replace shallow `gfyms doctor` camera check | Checking for `/dev/video*` does not prove that the sensor streams | Add format enumeration, one-frame capture, sensor identity, and error classification |
| P1 | Add zram and conservative service defaults for 4–8 GB models | Prevents browser/Plasma/Wine pressure from turning into swap storms | Compare PSI, swap-in/out and suspend/resume under a fixed workload |
| P1 | Cache Arch packages and prebuilt GFYMS packages in CI | Building the same package and downloading the same dependencies repeatedly dominates CI time | Measure cold vs warm build duration and cache hit rate |
| P2 | Build UKIs and signed boot artifacts as explicit CI outputs | Makes Secure Boot a testable release property | Verify signatures, boot in QEMU with Secure Boot where possible, retain previous UKI |
| P2 | Add bootable recovery mode and restore tests | A backup that has never been restored is not a recovery system | Monthly clean restore to a loopback/Btrfs test target |
| P2 | Add cloud integration as an optional package | Keeps networking, credentials and cache policy out of the core OS | Offline boot test, network-loss test, failed-upload retry, restore test |

The `mkinitcpio` messages in the supplied log are mostly normal for an Arch package transaction inside a chroot: systemd reload/restart operations are intentionally skipped because there is no running target system to restart. The “possibly missing firmware” messages are module-specific warnings for hardware such as `ast`, `mlxsw_spectrum`, `qed`, and other unrelated devices. They are not by themselves evidence that Surface Pro 7 firmware is missing. The build should still verify the actual Surface kernel modules and required firmware by inspecting the generated initramfs and testing the physical device.

## Legal and distribution boundary

The repository should not publish a blanket claim that it contains “official Microsoft drivers for Linux.” It should publish a component manifest with SHA-256 hashes, origin, license/provenance, redistribution status, intended use, and whether a file is a Linux firmware blob, calibration data, Windows user-mode binary, Windows kernel driver, or reverse-engineering reference. Vendor `.sys`, `.dll`, `.exe`, `.cat`, signed firmware and proprietary calibration files need a deliberate distribution decision. Where redistribution is not clearly permitted, the ISO should contain the native Linux implementation and instructions for a user to obtain permitted firmware or reference material themselves.

## Phased execution plan

**Phase 1 — make the build honest and reproducible.** Keep the CI ownership/artifact fix, add LFS-pointer validation, split package profiles, add ISO-content assertions, and publish a hardware qualification report. Do not add vendor Windows binaries to the ISO.

**Phase 2 — native Surface baseline.** Package the tested `linux-surface` kernel/userspace, improve `gfyms doctor`, and make SAM, touch, pen, cover, battery, audio, Wi-Fi/Bluetooth, sensors, suspend/resume and USB-C tests first-class. Add a minimal offline recovery environment.

**Phase 3 — IPU4 camera.** Import or rebase a legally distributable native Linux IPU4/IPU4P implementation, carry SP7 timing/sensor patches with attribution, and test raw capture before libcamera/PipeWire integration. Keep OV sensor configuration provenance explicit.

**Phase 4 — installer and signed boot.** Implement the TUI installer with dry-run/report modes, LUKS2/Btrfs or ext4, rollback entries and UKI generation. Add signing/enrollment documentation and CI signature verification.

**Phase 5 — recovery cloud.** Ship the optional `gfyms-cloud` package: Nextcloud selective sync for user data, restic encrypted snapshots for recovery, bounded caches, app passwords, offline boot, and automated restore tests. Never make cloud reachability a boot requirement.

**Phase 6 — compatibility research.** Keep WinMill/WinRunner/.NET/Windows-driver ABI work isolated behind an experimental package and a test harness. It must not be described as native Linux driver support until a real Linux device path exists and physical qualification passes.

## References

- [Nextcloud: Accessing files using WebDAV](https://docs.nextcloud.com/server/stable/user_manual/en/files/access_webdav.html) — official documentation recommends the desktop sync client for offline synchronization and documents WebDAV's network-dependent access model.
- [restic introduction](https://restic.readthedocs.io/en/stable/010_introduction.html) — encrypted repository workflow, snapshots, restore and integrity checks.
- [rclone mount and VFS](https://rclone.org/commands/rclone_mount/) — cache, buffering, write-back and filesystem-semantic limitations.
- [ArchWiki: Secure Boot](https://wiki.archlinux.org/title/Unified_Extensible_Firmware_Interface/Secure_Boot) — key enrollment, signing, `sbctl`, `systemd-sbsign` and trust-chain warnings.
- [ArchWiki: Unified kernel image](https://wiki.archlinux.org/title/Unified_kernel_image) — UKI composition, embedded command line, signing and systemd-boot discovery.
- [linux-surface IPU4 discussion](https://github.com/linux-surface/linux-surface/discussions/1353) — current community evidence for SP7 IPU4 work, sensor timing and remaining libcamera/IR issues.
- [libcamera FAQ](https://libcamera.org/faq.html) — separation of the open userspace camera stack from Linux kernel drivers and platform pipeline handlers.
