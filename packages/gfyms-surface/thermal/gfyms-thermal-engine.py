#!/usr/bin/env python3
"""Conservative Surface thermal policy loop.

This is a policy layer, not firmware control: it reads thermal-zone sensors and
uses powerprofilesctl when available. It never undervolts, writes MSRs, or
bypasses firmware safety limits.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path


PROFILES = ("power-saver", "balanced", "performance")


def temperatures() -> list[float]:
    values: list[float] = []
    for path in Path("/sys/class/thermal").glob("thermal_zone*/temp"):
        try:
            values.append(int(path.read_text().strip()) / 1000.0)
        except (OSError, ValueError):
            continue
    return values


def set_profile(profile: str) -> bool:
    try:
        result = subprocess.run(["powerprofilesctl", "set", profile], capture_output=True, text=True, timeout=5, check=False)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def choose_profile(hottest: float, current: str) -> str:
    # Hysteresis prevents rapid profile flapping around thresholds.
    if hottest >= 88.0:
        return "power-saver"
    if hottest >= 78.0:
        return "balanced"
    if current == "power-saver" and hottest > 68.0:
        return "balanced"
    return "performance" if hottest < 68.0 else "balanced"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interval", type=float, default=15.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--state", type=Path, default=Path("/run/gfyms-thermal/state.json"))
    args = parser.parse_args()
    current = "balanced"
    while True:
        values = temperatures()
        hottest = max(values) if values else 0.0
        selected = choose_profile(hottest, current)
        changed = selected != current and set_profile(selected)
        if changed:
            current = selected
        args.state.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        args.state.write_text(json.dumps({"hottest_c": hottest, "temperatures_c": values, "profile": current, "changed": changed, "timestamp": int(time.time())}, indent=2) + "\n", encoding="utf-8")
        if args.once:
            return 0
        time.sleep(max(args.interval, 5.0))


if __name__ == "__main__":
    raise SystemExit(main())
