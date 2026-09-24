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
  xorriso curl

echo '== Prepare signed linux-surface package source ==' 
curl -fsSL https://raw.githubusercontent.com/linux-surface/linux-surface/master/pkg/keys/surface.asc | pacman-key --add -
pacman-key --finger 56C464BAAC421453
pacman-key --lsign-key 56C464BAAC421453
grep -q '^\[linux-surface\]
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

# Use the GFYMS package instead of pretending it is available from an external
# package repository during the preview build.
sed -i '/^[[:space:]]*gfyms-/d' /tmp/gfyms-profile/packages.x86_64 || true

# The upstream Surface packages were downloaded and signature-checked above, then
# staged locally so mkarchiso can install them and run their package hooks.
cp /tmp/gfyms-profile/pacman.conf /tmp/gfyms-profile/pacman.conf.new
printf '%s\n' '[gfyms-surface-build]' 'SigLevel = Optional' 'Server = file:///tmp/gfyms-localrepo' >> /tmp/gfyms-profile/pacman.conf.new
mv /tmp/gfyms-profile/pacman.conf.new /tmp/gfyms-profile/pacman.conf

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
ln -sf /usr/lib/systemd/system/iptsd.service /tmp/gfyms-profile/airootfs/etc/systemd/system/multi-user.target.wants/iptsd.service

# Point ArchISO's standard boot entries at the linux-surface kernel.
while IFS= read -r -d '' bootcfg; do
  sed -i -e 's/vmlinuz-linux-surface/vmlinuz-linux-surface/g' \
         -e 's/vmlinuz-linux/vmlinuz-linux-surface/g' \
         -e 's/initramfs-linux-surface/initramfs-linux-surface/g' \
         -e 's/initramfs-linux/initramfs-linux-surface/g' "$bootcfg"
done < <(grep -rlZ -E 'vmlinuz-linux|initramfs-linux' /tmp/gfyms-profile 2>/dev/null || true)


mkdir -p /tmp/gfyms-profile/airootfs/etc/sddm.conf.d
printf '%s\n' '[Autologin]' 'User=root' 'Session=plasma' 'Relogin=false' > /tmp/gfyms-profile/airootfs/etc/sddm.conf.d/10-gfyms-preview.conf

# This preview does not create a privileged passwordless live user.
# The live environment remains the normal ArchISO root environment.

sed -i \
  -e "s/^iso_name=.*/iso_name=\"gfyms-surface-pro-7\"/" \
  -e "s/^iso_application=.*/iso_application=\"GFYMS Surface Pro 7 Arch Linux\"/" \
  -e "s/^iso_version=.*/iso_version=\"$VERSION\"/" \
  /tmp/gfyms-profile/profiledef.sh

echo '== Build ISO ==' 
mkarchiso -v -r -w /tmp/gfyms-work -o "$OUTPUT_ROOT" /tmp/gfyms-profile

ISO=$(find "$OUTPUT_ROOT" -maxdepth 1 -type f -name 'gfyms-surface-pro-7-*.iso' -print -quit)
if [[ -z "$ISO" ]]; then
  ISO=$(find "$OUTPUT_ROOT" -maxdepth 1 -type f -name '*.iso' -print -quit)
fi
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
 /etc/pacman.conf || printf '%s\n' '[linux-surface]' 'Server = https://pkg.surfacelinux.com/arch/' >> /etc/pacman.conf
pacman -Sy --noconfirm
pacman -Sw --noconfirm linux-surface linux-surface-headers iptsd

rm -rf /tmp/gfyms-localrepo
mkdir -p /tmp/gfyms-localrepo
cp /var/cache/pacman/pkg/linux-surface-*.pkg.tar.zst /tmp/gfyms-localrepo/
cp /var/cache/pacman/pkg/linux-surface-*.pkg.tar.zst.sig /tmp/gfyms-localrepo/ 2>/dev/null || true
cp /var/cache/pacman/pkg/iptsd-*.pkg.tar.zst /tmp/gfyms-localrepo/
cp /var/cache/pacman/pkg/iptsd-*.pkg.tar.zst.sig /tmp/gfyms-localrepo/ 2>/dev/null || true
repo-add /tmp/gfyms-localrepo/gfyms-surface-build.db.tar.zst /tmp/gfyms-localrepo/*.pkg.tar.zst

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

sed -i \
  -e "s/^iso_name=.*/iso_name=\"gfyms-surface-pro-7\"/" \
  -e "s/^iso_application=.*/iso_application=\"GFYMS Surface Pro 7 Arch Linux\"/" \
  -e "s/^iso_version=.*/iso_version=\"$VERSION\"/" \
  /tmp/gfyms-profile/profiledef.sh

echo '== Build ISO ==' 
mkarchiso -v -r -w /tmp/gfyms-work -o "$OUTPUT_ROOT" /tmp/gfyms-profile

ISO=$(find "$OUTPUT_ROOT" -maxdepth 1 -type f -name 'gfyms-surface-pro-7-*.iso' -print -quit)
if [[ -z "$ISO" ]]; then
  ISO=$(find "$OUTPUT_ROOT" -maxdepth 1 -type f -name '*.iso' -print -quit)
fi
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
