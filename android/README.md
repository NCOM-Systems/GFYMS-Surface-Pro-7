# GFYMS native Android build contract

This directory is the boundary for the optional GFYMS-native Android userspace. It is **not** included in the base Arch ISO yet because the repository does not currently contain a bootable AOSP-derived runtime, ART/Bionic framework image, package manager, Binder service group, or tested AIDL hardware adapters.

The base ISO must therefore remain a normal Arch/KDE system and must not claim APK execution. Adding an APK file to the ISO does not make it runnable.

## Required milestone before enabling Android in an ISO

The Android profile may be enabled only after a separate reproducible build produces, for x86_64:

1. ART, Bionic, Android framework services, package manager and signed system image;
2. Binder/binderfs, namespaces, cgroups, seccomp and SELinux policy validation;
3. a signed test APK install/launch/uninstall test;
4. desktop graphics and input ownership tests;
5. an explicit resource budget suitable for Surface Pro 7 memory;
6. recovery and rollback that cannot modify the Arch boot or Surface driver state;
7. hardware qualification for input, graphics, audio, sensors, camera and power adapters.

Until then, the ISO builder must fail closed or omit Android rather than silently shipping a nonfunctional APK menu.

## F-Droid policy

F-Droid is an optional **Android** application source. It is not a Linux package manager and cannot run on the Arch desktop without the Android runtime. After the native runtime reaches the package-installation milestone, GFYMS should:

- install the official signed F-Droid client inside the Android userspace;
- verify the downloaded APK and record its SHA-256 and signing provenance;
- keep F-Droid repositories, package database and app data under the Android subsystem;
- permit the user to add or remove repositories without changing the base OS;
- keep Google Mobile Services optional and non-required;
- report ARM-only APKs as unsupported on the x86_64 Surface Pro 7 unless a separately approved translation layer exists.

The official F-Droid client and repository metadata must be pinned and reviewed before being shipped in a release. Do not download an unpinned APK during ISO installation.

## Current tools

Use the read-only inspector before a future installation flow:

```bash
./tools/gfyms-apk-inspect.py ./some-app.apk --json
```

It reports whether the file is a valid APK-shaped ZIP, whether it contains DEX and a manifest, which native ABIs it contains, and whether signature files are present. It does not verify signatures, install packages, or execute code. The future Android installer must use Android's package manager and `apksigner`/platform verification, not this advisory tool alone.

See [`docs/GFYMS-NATIVE-ANDROID.md`](../docs/GFYMS-NATIVE-ANDROID.md) for the full architecture and staged adapter plan.
