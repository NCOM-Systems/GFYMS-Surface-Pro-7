#!/usr/bin/env python3
"""Read-only GFYMS package/API artifact inspector.

This tool intentionally does not install, execute, modify, or trust artifacts.
Windows-only claims such as Authenticode/WinVerifyTrust are left as explicit
"not-evaluated" evidence for a Windows adapter.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAGIC_MZ = b"MZ"
MAGIC_MSI = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def digest(path: Path) -> dict[str, Any]:
    sha256 = hashlib.sha256()
    sha512 = hashlib.sha512()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk)
            sha256.update(chunk)
            sha512.update(chunk)
    return {"size": size, "sha256": sha256.hexdigest(), "sha512": sha512.hexdigest()}


def read_prefix(path: Path, length: int = 4096) -> bytes:
    with path.open("rb") as handle:
        return handle.read(length)


def pe_metadata(path: Path, prefix: bytes) -> dict[str, Any] | None:
    if len(prefix) < 0x40 or prefix[:2] != MAGIC_MZ:
        return None
    pe_offset = struct.unpack_from("<I", prefix, 0x3C)[0]
    needed = pe_offset + 26
    if len(prefix) < needed:
        with path.open("rb") as handle:
            handle.seek(pe_offset)
            header = handle.read(26)
    else:
        header = prefix[pe_offset : pe_offset + 26]
    if len(header) < 26 or header[:4] != b"PE\0\0":
        return None
    machine, sections = struct.unpack_from("<HH", header, 4)
    optional_size = struct.unpack_from("<H", header, 20)[0]
    optional_offset = pe_offset + 24
    with path.open("rb") as handle:
        handle.seek(optional_offset)
        optional = handle.read(optional_size)
    magic = struct.unpack_from("<H", optional, 0)[0] if len(optional) >= 2 else None
    machine_name = {0x8664: "amd64", 0x14C: "x86", 0xAA64: "arm64"}.get(machine, f"0x{machine:04x}")
    entry_rva = struct.unpack_from("<I", optional, 16)[0] if len(optional) >= 20 else None
    return {
        "machine": machine_name,
        "machine_value": f"0x{machine:04x}",
        "sections": sections,
        "optional_header": "pe32+" if magic == 0x20B else "pe32" if magic == 0x10B else f"0x{magic:04x}" if magic is not None else None,
        "entry_rva": entry_rva,
        "pe_offset": pe_offset,
    }


def json_metadata(path: Path) -> dict[str, Any] | None:
    if path.name.lower().endswith(".runtimeconfig.json"):
        kind = "runtimeconfig"
    elif path.name.lower().endswith(".deps.json"):
        kind = "deps"
    else:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return {"kind": kind, "parse": "failed", "error": str(error)}
    result: dict[str, Any] = {"kind": kind, "parse": "ok"}
    if kind == "runtimeconfig":
        options = data.get("runtimeOptions", {})
        result["frameworks"] = options.get("frameworks", [])
        if "framework" in options:
            result["framework"] = options["framework"]
        result["roll_forward"] = options.get("rollForward")
        result["config_properties"] = options.get("configProperties", {})
    else:
        result["runtime_target"] = data.get("runtimeTarget")
        result["targets"] = sorted(data.get("targets", {}).keys())
        result["libraries"] = sorted(data.get("libraries", {}).keys())
    return result


def classify(path: Path, prefix: bytes, pe: dict[str, Any] | None, json_info: dict[str, Any] | None) -> list[str]:
    suffix = path.suffix.lower()
    kinds: list[str] = []
    if prefix.startswith(MAGIC_MSI):
        kinds.append("msi-or-ole-package")
    if pe:
        kinds.append("pe")
        if suffix == ".sys":
            kinds.append("windows-kernel-driver")
        elif suffix == ".dll":
            kinds.append("windows-dll")
        elif suffix == ".exe":
            kinds.append("windows-executable")
    if json_info:
        kinds.append(f"dotnet-{json_info['kind']}")
    if suffix == ".msp":
        kinds.append("msi-patch-candidate")
    return kinds or ["unknown"]


def safe_relative(path: Path, root: Path) -> str:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root.resolve())
    except ValueError as error:
        raise SystemExit(f"artifact is outside staging root: {resolved}") from error
    return relative.as_posix()


def inspect(path: Path, output: Path, staging_root: Path) -> dict[str, Any]:
    path = path.resolve()
    if not path.is_file():
        raise SystemExit(f"missing artifact: {path}")
    output.mkdir(parents=True, exist_ok=True)
    prefix = read_prefix(path)
    pe = pe_metadata(path, prefix)
    json_info = json_metadata(path)
    record: dict[str, Any] = {
        "schema": "gfyms.api.inspect.v1",
        "inspected_utc": datetime.now(timezone.utc).isoformat(),
        "artifact": {"name": path.name, "relative_path": safe_relative(path, staging_root), **digest(path)},
        "classification": classify(path, prefix, pe, json_info),
        "pe": pe,
        "dotnet": json_info,
        "trust": {"authenticode": "not-evaluated", "win_verify_trust": "not-available-on-linux"},
        "execution": {"performed": False, "reason": "read-only analyzer"},
        "evidence": {"source": "local-staged-artifact", "path_policy": "contained-by-staging-root"},
    }
    (output / "manifest.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "classification.json").write_text(json.dumps({"classification": record["classification"], "pe": pe, "dotnet": json_info}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--staging-root", type=Path, required=True)
    args = parser.parse_args()
    record = inspect(args.artifact, args.output, args.staging_root)
    print(json.dumps({"status": "ok", "artifact": record["artifact"], "classification": record["classification"], "output": str(args.output.resolve())}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
