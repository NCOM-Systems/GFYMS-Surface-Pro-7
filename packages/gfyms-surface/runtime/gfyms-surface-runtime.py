#!/usr/bin/env python3
"""Stage hash-pinned, user-approved Microsoft Surface runtime payloads.

The manifest must contain exact HTTPS URLs and SHA-256 values. This tool only
stages verified bytes; it never executes installers, imports kernel modules, or
claims Authenticode verification on Linux.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import ssl
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "gfyms.surface.runtime.v1":
        raise ValueError("unsupported manifest schema")
    entries = data.get("payloads")
    if not isinstance(entries, list):
        raise ValueError("manifest payloads must be a list")
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("each payload must be an object")
        for field in ("id", "url", "sha256", "filename", "kind"):
            if not entry.get(field):
                raise ValueError(f"payload is missing {field}")
        parsed = urlparse(entry["url"])
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError(f"payload {entry['id']} must use an HTTPS URL")
        expected = entry["sha256"].lower()
        if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
            raise ValueError(f"payload {entry['id']} has an invalid SHA-256")
        if Path(entry["filename"]).name != entry["filename"]:
            raise ValueError(f"payload {entry['id']} filename must be a basename")
    return data


def download(url: str, destination: Path) -> None:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "GFYMS-Surface-Runtime/1", "Accept": "*/*"},
    )
    context = ssl.create_default_context()
    with urllib.request.urlopen(request, timeout=180, context=context) as response:
        with destination.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    return
                handle.write(chunk)


def stage(manifest_path: Path, destination: Path, apply: bool) -> int:
    manifest = load_manifest(manifest_path)
    payloads = manifest["payloads"]
    destination.mkdir(mode=0o750, parents=True, exist_ok=True)
    if not payloads:
        print("manifest contains no payloads; add exact official URLs and hashes before installation")
        return 0
    for entry in payloads:
        target = destination / entry["filename"]
        if target.exists() and sha256(target) == entry["sha256"].lower():
            print(f"verified existing: {entry['id']}")
            continue
        if not apply:
            print(f"plan: download {entry['id']} -> {target}")
            continue
        with tempfile.NamedTemporaryFile(dir=destination, prefix=f".{entry['filename']}.", delete=False) as temporary:
            temporary_path = Path(temporary.name)
        try:
            download(entry["url"], temporary_path)
            actual = sha256(temporary_path)
            if actual != entry["sha256"].lower():
                raise RuntimeError(f"SHA-256 mismatch for {entry['id']}: expected {entry['sha256']}, got {actual}")
            os.chmod(temporary_path, 0o640)
            os.replace(temporary_path, target)
            print(f"staged verified: {entry['id']}")
        finally:
            temporary_path.unlink(missing_ok=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--destination", type=Path, default=Path("/var/lib/gfyms/surface-runtime"))
    parser.add_argument("--apply", action="store_true", help="download and stage; without this flag only print the plan")
    args = parser.parse_args()
    return stage(args.manifest, args.destination, args.apply)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, urllib.error.URLError) as error:
        print(f"gfyms-surface-runtime: {error}", file=sys.stderr)
        raise SystemExit(1)
