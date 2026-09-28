#!/usr/bin/env python3
"""GFYMS evidence-first recovery assistant.

The default operations never modify the system. They collect diagnostics,
create a user-selected backup bundle, and write a proposed plan. Applying a
repair requires an explicit --yes flag and is intentionally limited to safe,
reviewable actions in a later implementation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import tarfile
import time
from pathlib import Path
from typing import Any

SCHEMA = "gfyms.recovery.v1"
DEFAULT_PATHS = [
    "/etc/fstab",
    "/etc/default/grub",
    "/etc/mkinitcpio.conf",
    "/etc/pacman.conf",
    "/etc/gfyms",
]


def run(command: list[str]) -> dict[str, Any]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
        return {"command": command, "returncode": result.returncode, "stdout": result.stdout[-12000:], "stderr": result.stderr[-4000:]}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"command": command, "error": str(error)}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def diagnose(output: Path) -> dict[str, Any]:
    output.mkdir(mode=0o750, parents=True, exist_ok=True)
    evidence: dict[str, Any] = {
        "schema": SCHEMA,
        "created_epoch": int(time.time()),
        "host": {"hostname": platform.node(), "kernel": platform.release(), "architecture": platform.machine()},
        "checks": {
            "boot_current": run(["systemctl", "is-system-running"]),
            "failed_units": run(["systemctl", "--failed", "--no-legend"]),
            "recent_errors": run(["journalctl", "-b", "-p", "err", "--no-pager", "-n", "80"]),
            "previous_boot_errors": run(["journalctl", "-b", "-1", "-p", "err", "--no-pager", "-n", "80"]),
            "pacman_log_tail": run(["sh", "-c", "tail -n 120 /var/log/pacman.log 2>/dev/null || true"]),
            "boot_entries": run(["bootctl", "list", "--no-pager"]),
            "disk_space": run(["df", "-h", "/", "/boot"]),
        },
        "risk": {
            "automatic_repair": "disabled",
            "data_loss_expected": False,
            "note": "This report is diagnostic evidence only; no repair or rollback was performed.",
        },
    }
    path = output / "diagnosis.json"
    path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return evidence


def backup(output: Path, paths: list[str]) -> dict[str, Any]:
    output.mkdir(mode=0o750, parents=True, exist_ok=True)
    archive = output / "gfyms-settings-backup.tar.gz"
    included: list[str] = []
    with tarfile.open(archive, "w:gz") as tar:
        for raw in paths:
            path = Path(raw)
            if not path.exists():
                continue
            tar.add(path, arcname=path.relative_to("/") if path.is_absolute() else path)
            included.append(str(path))
    manifest = {"schema": SCHEMA, "kind": "settings-backup", "archive": archive.name, "sha256": sha256(archive), "included": included, "data_loss_expected": False}
    (output / "backup-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def plan(diagnosis_path: Path, output: Path) -> dict[str, Any]:
    diagnosis = json.loads(diagnosis_path.read_text(encoding="utf-8"))
    failed = diagnosis.get("checks", {}).get("failed_units", {}).get("stdout", "").strip()
    actions = [
        {"id": "preserve-evidence", "action": "keep-diagnosis-and-backup", "risk": "none", "automatic": True},
        {"id": "review-pacman-transaction", "action": "identify-last-package-change", "risk": "none", "automatic": False},
        {"id": "rollback-package-set", "action": "restore-only-after-user-review", "risk": "requires-confirmation", "automatic": False},
        {"id": "rebuild-initramfs", "action": "rebuild-after-package-review", "risk": "requires-confirmation", "automatic": False},
    ]
    result = {"schema": SCHEMA, "kind": "repair-plan", "created_epoch": int(time.time()), "signals": {"failed_units": failed}, "actions": actions, "requires_user_confirmation": True, "automatic_repair": False}
    output.mkdir(mode=0o750, parents=True, exist_ok=True)
    (output / "repair-plan.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    diagnose_parser = sub.add_parser("diagnose")
    diagnose_parser.add_argument("--output", type=Path, required=True)
    backup_parser = sub.add_parser("backup")
    backup_parser.add_argument("--output", type=Path, required=True)
    backup_parser.add_argument("--path", action="append", dest="paths", default=[])
    plan_parser = sub.add_parser("plan")
    plan_parser.add_argument("--diagnosis", type=Path, required=True)
    plan_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "diagnose":
        result = diagnose(args.output)
    elif args.command == "backup":
        result = backup(args.output, args.paths or DEFAULT_PATHS)
    else:
        result = plan(args.diagnosis, args.output)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
