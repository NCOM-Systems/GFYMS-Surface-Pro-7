#!/usr/bin/env python3
import hashlib
import json
import os
import re
import subprocess
import tempfile
import urllib.request
from pathlib import Path

API = "https://api.github.com/repos/pfn000/GFYMS-Surface-Pro-7/releases"
CONFIG = Path("/etc/gfyms/update.conf")
STATE = Path("/var/lib/gfyms/update-state.json")

def read_config():
    cfg = {"CHECK": "1", "AUTO_INSTALL": "0", "CHANNEL": "stable"}
    if CONFIG.exists():
        for raw in CONFIG.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line: continue
            key, value = line.split("=", 1)
            cfg[key.strip()] = value.strip()
    return cfg

def version_key(value):
    nums = re.findall(r"\d+", value)
    return tuple(int(x) for x in nums) if nums else (0,)

def fetch_json(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "GFYMS-Auto-Update"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)

def download(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": "GFYMS-Auto-Update"})
    with urllib.request.urlopen(req, timeout=120) as response:
        Path(path).write_bytes(response.read())

def find_asset(assets, name):
    for asset in assets:
        if asset.get("name") == name: return asset.get("browser_download_url")
    return None

def main():
    cfg = read_config()
    if cfg.get("CHECK", "1") != "1": return
    releases = fetch_json(API)
    stable = [r for r in releases if not r.get("draft") and not r.get("prerelease") and r.get("assets")]
    if not stable: raise RuntimeError("No stable GFYMS release is available.")
    stable.sort(key=lambda r: version_key(r.get("tag_name", "")), reverse=True)
    latest = stable[0]
    tag = latest.get("tag_name", "")
    installed = subprocess.run(["pacman", "-Q", "gfyms-surface"], capture_output=True, text=True, check=False).stdout.strip()
    installed_ver = installed.split()[1] if len(installed.split()) >= 2 else "0"

    state = {"installed": installed_ver, "latest": tag, "available": version_key(tag) > version_key(installed_ver), "checked": os.path.getmtime(CONFIG) if CONFIG.exists() else None}
    if state["available"] and cfg.get("AUTO_INSTALL", "0") == "1":
        assets = latest.get("assets", [])
        package = next((a for a in assets if a.get("name", "").startswith("gfyms-surface-") and a.get("name", "").endswith(".pkg.tar.zst")), None)
        sums_url = find_asset(assets, "SHA256SUMS")
        if not package or not sums_url: raise RuntimeError("Release is missing package or SHA256SUMS asset.")
        with tempfile.TemporaryDirectory(prefix="gfyms-update-") as temp:
            package_path = Path(temp) / package["name"]
            sums_path = Path(temp) / "SHA256SUMS"
            download(package["browser_download_url"], package_path)
            download(sums_url, sums_path)
            expected = None
            for line in sums_path.read_text(encoding="utf-8").splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[-1] == package["name"]: expected = parts[0].lower(); break
            if not expected: raise RuntimeError("Package checksum was not found in SHA256SUMS.")
            actual = hashlib.sha256(package_path.read_bytes()).hexdigest()
            if actual != expected: raise RuntimeError("SHA-256 verification failed.")
            subprocess.run(["/usr/libexec/gfyms-update-helper", "install", str(package_path)], check=True)
            state["installed"] = tag
            state["available"] = False
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__":
    try: main()
    except Exception as exc:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps({"error": str(exc)}, indent=2) + "\n", encoding="utf-8")
        raise