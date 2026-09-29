#!/usr/bin/env python3
"""Inspect APK structure and native ABIs without installing or executing it."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

ABIS = ("x86_64", "x86", "arm64-v8a", "armeabi-v7a", "armeabi", "mips64", "mips")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    if not args.apk.is_file():
        parser.error(f"APK not found: {args.apk}")

    result: dict[str, object] = {
        "path": str(args.apk),
        "sha256": hashlib.sha256(args.apk.read_bytes()).hexdigest(),
        "size": args.apk.stat().st_size,
        "valid_zip": False,
        "has_manifest": False,
        "has_dex": False,
        "abis": [],
        "signature_files": [],
        "install_policy": "unknown",
    }
    try:
        with zipfile.ZipFile(args.apk) as archive:
            names = archive.namelist()
            result["valid_zip"] = archive.testzip() is None
            result["has_manifest"] = "AndroidManifest.xml" in names
            result["has_dex"] = any(name.startswith("classes") and name.endswith(".dex") for name in names)
            result["abis"] = sorted({abi for name in names for abi in ABIS if name.startswith(f"lib/{abi}/")})
            result["signature_files"] = sorted(
                name for name in names
                if name.startswith("META-INF/") and name.upper().endswith((".RSA", ".DSA", ".EC"))
            )
    except (zipfile.BadZipFile, OSError) as exc:
        result["error"] = str(exc)

    if result["valid_zip"] and result["has_manifest"] and result["has_dex"]:
        abis = set(result["abis"])
        if not abis or "x86_64" in abis or "x86" in abis:
            result["install_policy"] = "eligible-for-gfyms-x86_64-review"
        else:
            result["install_policy"] = "arm-or-unsupported-native-abi"
    else:
        result["install_policy"] = "invalid-or-incomplete-apk"

    if args.as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        for key, value in result.items():
            print(f"{key}={value}")

    # This tool is intentionally advisory. It never installs, signs, or runs APKs.
    return 0 if "error" not in result else 2


if __name__ == "__main__":
    raise SystemExit(main())
