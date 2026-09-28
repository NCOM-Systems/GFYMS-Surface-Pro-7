# GFYMS private cloud vault

This is a reference deployment for a private Nextcloud service backing GFYMS user files and recovery snapshots. It is not a swap device and it does not expand physical RAM. It offloads **disk storage and cold data**, while keeping active applications and caches local for reliability.

## Architecture

```text
GFYMS Surface Pro 7
  ├─ local system + active working set
  ├─ Nextcloud desktop client / WebDAV for user files
  ├─ selective sync for only active folders
  └─ restic encrypted snapshots for recovery
          │ HTTPS/TLS
          ▼
Private server
  ├─ reverse proxy with TLS and HSTS
  ├─ Nextcloud
  ├─ MariaDB (private Docker network)
  └─ Redis (private Docker network)
          │
          └─ encrypted server-side backup target
```

## Deploy

```bash
cp .env.example .env
chmod 600 .env
$EDITOR .env
# Pin NEXTCLOUD_IMAGE, MARIADB_IMAGE, and REDIS_IMAGE to reviewed immutable digests.
docker compose --env-file .env -f compose.yaml config
docker compose --env-file .env -f compose.yaml up -d
```

The compose file binds HTTP to loopback only. Put a separately managed reverse proxy in front of it, issue TLS certificates, and set `NEXTCLOUD_TRUSTED_DOMAINS` to the real hostname. Do not expose the database or Redis ports publicly.

## Storage policy

- Use the Nextcloud desktop client with selective sync for normal documents.
- Keep active build trees, package caches, browser profiles, swap, and databases local; mounting them over WebDAV is unsafe and slow.
- For cold media and archives, use an explicit `Cloud Vault` folder and an eviction policy after successful upload and checksum verification.
- Use encrypted `restic` repositories for system/recovery snapshots. Nextcloud is the transport/storage endpoint, not the only backup copy.
- Maintain at least one independent backup target. A single Nextcloud server is not a backup.
- Enable Nextcloud MFA, app passwords, brute-force protection, automatic updates, and admin notifications.
- Prefer a separate non-admin sync account for the Surface client.

## Recovery model

1. Snapshot the manifest, package list, `/etc`, bootloader configuration, and user-selected recovery folders locally.
2. Encrypt and upload snapshots to a dedicated Nextcloud account/repository.
3. Verify the uploaded snapshot and record its hash in the local recovery journal.
4. Keep the newest verified snapshot plus a second historical snapshot.
5. Test restoration to a disposable directory before declaring a snapshot recoverable.

## Security boundary

The client must never put cloud credentials in the ISO or a world-readable systemd unit. Use a user-scoped Nextcloud app password stored in the desktop client/keyring. Use TLS certificate validation; do not add a `--no-check-certificate` escape hatch. The server's database, Redis, and Docker socket remain private.

## What this does not do

- It does not turn the cloud into RAM or make an offline Surface operate normally from remote files.
- It does not replace local boot-critical files, `/usr`, `/var/lib`, swap, or driver payloads with WebDAV mounts.
- It does not guarantee recovery unless restore tests and an independent backup succeed.
