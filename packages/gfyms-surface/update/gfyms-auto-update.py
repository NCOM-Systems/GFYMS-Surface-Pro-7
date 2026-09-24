#!/usr/bin/env python3
import hashlib
import json
import re
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

API = 'https://api.github.com/repos/pfn000/GFYMS-Surface-Pro-7/releases'
CONFIG = Path('/etc/gfyms/update.conf')
STATE = Path('/var/lib/gfyms/update-state.json')

def read_config():
    cfg = {'CHECK': '1', 'AUTO_INSTALL': '0', 'CHANNEL': 'stable'}
    if CONFIG.exists():
        for raw in CONFIG.read_text(encoding='utf-8').splitlines():
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            cfg[key.strip()] = value.strip()
    return cfg

def version_key(value):
    normalized = value.lstrip('v').split('-', 1)[0]
    nums = re.findall(r'\d+', normalized)
    return tuple(int(x) for x in nums) if nums else (0,)

def fetch_json(url):
    req = urllib.request.Request(url, headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'GFYMS-Auto-Update'})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)

def download(url, path):
    req = urllib.request.Request(url, headers={'User-Agent': 'GFYMS-Auto-Update'})
    with urllib.request.urlopen(req, timeout=120) as response:
        Path(path).write_bytes(response.read())

def asset_map(assets):
    return {a.get('name', ''): a.get('browser_download_url') for a in assets}

def main():
    cfg = read_config()
    if cfg.get('CHECK', '1') != '1':
        return
    releases = fetch_json(API)
    stable = [r for r in releases if not r.get('draft') and not r.get('prerelease') and r.get('assets')]
    if not stable:
        raise RuntimeError('No stable GFYMS release is available.')
    stable.sort(key=lambda r: version_key(r.get('tag_name', '')), reverse=True)
    latest = stable[0]
    tag = latest.get('tag_name', '')

    installed_output = subprocess.run(['pacman', '-Q', 'gfyms-surface'], capture_output=True, text=True, check=False).stdout.split()
    installed_ver = installed_output[1] if len(installed_output) >= 2 else '0'
    available = version_key(tag) > version_key(installed_ver)

    state = {'installed': installed_ver, 'latest': tag, 'available': available, 'checked': int(time.time())}
    if not available or cfg.get('AUTO_INSTALL', '0') != '1':
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(state, indent=2) + '\n', encoding='utf-8')
        return

    assets = latest.get('assets', [])
    urls = asset_map(assets)
    manifest_url = urls.get('GFYMS-MANIFEST.json')
    manifest = None
    if manifest_url:
        with tempfile.TemporaryDirectory(prefix='gfyms-update-') as temp:
            manifest_path = Path(temp) / 'GFYMS-MANIFEST.json'
            download(manifest_url, manifest_path)
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))

    package_names = []
    expected_hashes = {}
    if manifest and manifest.get('packages'):
        package_names = [p['name'] for p in manifest['packages'] if p.get('name')]
        expected_hashes = {p['name']: p.get('sha256', '').lower() for p in manifest['packages']}
    else:
        package_names = sorted(name for name in urls if name.startswith('gfyms-') and name.endswith('.pkg.tar.zst'))

    sums_url = urls.get('SHA256SUMS')
    if sums_url:
        with tempfile.TemporaryDirectory(prefix='gfyms-sums-') as temp:
            sums_path = Path(temp) / 'SHA256SUMS'
            download(sums_url, sums_path)
            for line in sums_path.read_text(encoding='utf-8').splitlines():
                parts = line.split()
                if len(parts) >= 2:
                    expected_hashes.setdefault(parts[-1], parts[0].lower())

    if not package_names:
        raise RuntimeError('Release contains no GFYMS package assets.')

    with tempfile.TemporaryDirectory(prefix='gfyms-update-') as temp:
        package_paths = []
        for name in package_names:
            url = urls.get(name)
            if not url:
                raise RuntimeError(f'Release is missing package asset: {name}')
            path = Path(temp) / name
            download(url, path)
            expected = expected_hashes.get(name)
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if expected and expected != actual:
                raise RuntimeError(f'SHA-256 verification failed for {name}.')
            package_paths.append(str(path))

        subprocess.run(['/usr/libexec/gfyms-update-helper', 'install', *package_paths], check=True)
        state['installed'] = tag
        state['available'] = False

    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2) + '\n', encoding='utf-8')

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps({'error': str(exc), 'checked': int(time.time())}, indent=2) + '\n', encoding='utf-8')
        raise
