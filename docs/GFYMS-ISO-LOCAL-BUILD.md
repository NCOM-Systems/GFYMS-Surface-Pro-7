# GFYMS ISO local build and Dropbox export

## Local build

On CachyOS or another Arch-based build host:

    sudo pacman -S --needed docker git
    sudo systemctl enable --now docker.service

Then:

    git checkout feat/abi-map-v2
    ./tools/build-gfyms-release-local.sh

The ISO and companion artifacts appear in release-build/. Verify before distribution:

    (cd release-build && sha256sum -c SHA256SUMS)

The local wrapper mounts the source checkout read-only and gives the disposable Arch container only the release-build/ output directory as writable.

## GitHub and large ISO files

The existing GitHub release workflow already splits an oversized ISO into 1900 MiB numbered fragments and verifies that concatenating those fragments reproduces the original SHA-256.

Dropbox is therefore an alternate distribution channel, not a requirement for building.

## Dropbox

Configure an rclone Dropbox remote once:

    rclone config

Copy the complete release directory:

    rclone copy --progress ./release-build "dropbox:GFYMS/releases/<VERSION>"

Verify the remote copy:

    rclone check ./release-build "dropbox:GFYMS/releases/<VERSION>" --one-way

Keep SHA256SUMS and GFYMS-MANIFEST.json beside the ISO.

## Firewall baseline

The image now includes nftables with default-drop inbound and forwarding, established/related traffic, loopback, necessary ICMP/ICMPv6 control traffic, DHCP replies, and unrestricted outbound traffic. SSH, Samba, mDNS, KDE remote-control, and other service ports are not opened by default.

This is deliberately a kernel-near firewall layer instead of adding a larger firewall-management daemon.

## Hardening gate

Before a production label, qualify listening services, systemd service isolation, package signatures, update policy, application sandboxing, physical Surface hardware, VM smoke tests, and artifact hash/signature verification.
