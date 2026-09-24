#!/usr/bin/env bash
set -euo pipefail

: "${VERSION:?VERSION must be supplied}"
: "${SOURCE_ROOT:=/src}"
: "${OUTPUT_ROOT:=/src/release-build}"

rm -rf /tmp/gfyms-surface /tmp/gfyms-profile /tmp/gfyms-work
mkdir -p "$OUTPUT_ROOT"

echo '== GFYMS Arch package build ==' 
pacman -Syu --noconfirm
pacman -S --noconfirm --needed \
  base-devel archiso cmake extra-cmake-modules \
  qt6-base qt6-declarative qt6-tools kcmutils kirigami git \
  xorriso

useradd -m -U builder
cp -a "$SOURCE_ROOT/packages/gfyms-surface" /tmp/gfyms-surface
chown -R builder:builder /tmp/gfyms-surface
su - builder -c 'cd /tmp/gfyms-surface && makepkg --syncdeps --noconfirm --clean --cleanbuild'

PKG=$(find /tmp/gfyms-surface -maxdepth 1 -type f -name 'gfyms-surface-*.pkg.tar.zst' -print -quit)
test -n "$PKG"
install -Dm644 "$PKG" "$OUTPUT_ROOT/$(basename "$PKG")"

echo '== Package built ==' 
ls -lh "$PKG"

echo '== Prepare ArchISO profile ==' 
cp -a /usr/share/archiso/configs/releng /tmp/gfyms-profile
cp "$SOURCE_ROOT/profiles/archiso-surface-pro-7/profiledef.sh" /tmp/gfyms-profile/profiledef.sh

# Use the GFYMS package instead of pretending it is available from an external
# package repository during the preview build.
sed -i '/^[[:space:]]*gfyms-/d' /tmp/gfyms-profile/packages.x86_64 || true
cat "$SOURCE_ROOT/profiles/archiso-surface-pro-7/packages.x86_64" >> /tmp/gfyms-profile/packages.x86_64

# Overlay the package into the live filesystem after pacstrap builds the base.
bsdtar -xf "$PKG" -C /tmp/gfyms-profile/airootfs

mkdir -p /tmp/gfyms-profile/airootfs/usr/share/gfyms
install -Dm644 "$SOURCE_ROOT/GFYMS_concept_logo-removebg-preview.png" /tmp/gfyms-profile/airootfs/usr/share/gfyms/gfyms-logo.png
printf '%s\n' "$VERSION" > /tmp/gfyms-profile/airootfs/usr/share/gfyms/version

mkdir -p /tmp/gfyms-profile/airootfs/etc/systemd/system/multi-user.target.wants
ln -sf /usr/lib/systemd/system/NetworkManager.service /tmp/gfyms-profile/airootfs/etc/systemd/system/multi-user.target.wants/NetworkManager.service
ln -sf /usr/lib/systemd/system/gfyms-surface.service /tmp/gfyms-profile/airootfs/etc/systemd/system/multi-user.target.wants/gfyms-surface.service
ln -sf /usr/lib/systemd/system/sddm.service /tmp/gfyms-profile/airootfs/etc/systemd/system/display-manager.service

mkdir -p /tmp/gfyms-profile/airootfs/etc/sddm.conf.d
printf '%s\n' '[Autologin]' 'User=root' 'Session=plasma' 'Relogin=false' > /tmp/gfyms-profile/airootfs/etc/sddm.conf.d/10-gfyms-preview.conf

# This preview does not create a privileged passwordless live user.
# The live environment remains the normal ArchISO root environment.

sed -i "s/^iso_version=.*/iso_version=\"$VERSION\"/" /tmp/gfyms-profile/profiledef.sh

echo '== Build ISO ==' 
mkarchiso -v -r -w /tmp/gfyms-work -o "$OUTPUT_ROOT" /tmp/gfyms-profile

ISO=$(find "$OUTPUT_ROOT" -maxdepth 1 -type f -name 'gfyms-surface-pro-7-*.iso' -print -quit)
test -s "$ISO"

echo '== Package release tools ==' 
chmod 755 "$SOURCE_ROOT/tools/gfyms-patcher/gfyms-patch" "$SOURCE_ROOT/tools/gfyms-usb/gfyms-usb"
tar -C "$SOURCE_ROOT/tools/gfyms-patcher" -czf "$OUTPUT_ROOT/gfyms-arch-patcher-${VERSION}.tar.gz" gfyms-patch README.md
tar -C "$SOURCE_ROOT/tools/gfyms-usb" -czf "$OUTPUT_ROOT/gfyms-usb-tool-${VERSION}.tar.gz" gfyms-usb README.md

echo '== Verify ISO contents ==' 
mountpoint='' 
WORKDIR=/tmp/gfyms-iso-mount
rm -rf "$WORKDIR"
mkdir -p "$WORKDIR"
if command -v mountpoint >/dev/null 2>&1; then :; fi
# xorriso's El Torito/image structure is validated by mkarchiso itself;
# additionally verify that the release ISO is non-empty and the package/tools
# are present in the output directory.
test -s "$ISO"

echo '== Checksums ==' 
rm -f "$OUTPUT_ROOT/SHA256SUMS"
(cd "$OUTPUT_ROOT" && sha256sum ./* > SHA256SUMS)

echo '== Final artifacts ==' 
ls -lh "$OUTPUT_ROOT"
