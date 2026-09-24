#!/usr/bin/env bash
set -euo pipefail

: "${VERSION:?VERSION must be supplied}"
: "${SOURCE_ROOT:=/src}"
: "${OUTPUT_ROOT:=/src/release-build}"

PROFILE=/tmp/gfyms-profile
WORK=/tmp/gfyms-work
LOCAL_REPO=/tmp/gfyms-localrepo
PKG_BUILD=/tmp/gfyms-surface

rm -rf "$PROFILE" "$WORK" "$LOCAL_REPO" "$PKG_BUILD"
rm -rf "$OUTPUT_ROOT"
mkdir -p "$OUTPUT_ROOT"

echo '== Bootstrap Arch build environment ==' 
pacman -Syu --noconfirm
pacman -S --noconfirm --needed base-devel archiso cmake extra-cmake-modules qt6-base qt6-declarative qt6-tools kcmutils kirigami git xorriso curl

echo '== Configure linux-surface signing key ==' 
pacman-key --init
curl -fsSL https://raw.githubusercontent.com/linux-surface/linux-surface/master/pkg/keys/surface.asc | pacman-key --add -
pacman-key --finger 56C464BAAC421453
pacman-key --lsign-key 56C464BAAC421453
if ! grep -q '^\[linux-surface\]$' /etc/pacman.conf; then cat >> /etc/pacman.conf <<'EOF'

[linux-surface]
Server = https://pkg.surfacelinux.com/arch/
EOF
fi
pacman -Sy --noconfirm
pacman -Sw --noconfirm linux-surface linux-surface-headers iptsd

echo '== Stage verified Surface packages for ArchISO ==' 
mkdir -p "$LOCAL_REPO"
cp /var/cache/pacman/pkg/linux-surface-*.pkg.tar.zst "$LOCAL_REPO/"
cp /var/cache/pacman/pkg/linux-surface-*.pkg.tar.zst.sig "$LOCAL_REPO/" 2>/dev/null || true
cp /var/cache/pacman/pkg/iptsd-*.pkg.tar.zst "$LOCAL_REPO/"
cp /var/cache/pacman/pkg/iptsd-*.pkg.tar.zst.sig "$LOCAL_REPO/" 2>/dev/null || true
repo-add "$LOCAL_REPO/gfyms-surface-build.db.tar.zst" "$LOCAL_REPO"/*.pkg.tar.zst

echo '== Build GFYMS native package ==' 
useradd -m -U builder
cp -a "$SOURCE_ROOT/packages/gfyms-surface" "$PKG_BUILD"
chown -R builder:builder "$PKG_BUILD"
su - builder -c "cd '$PKG_BUILD' && makepkg --syncdeps --noconfirm --clean --cleanbuild"
GFYMS_PKG=$(find "$PKG_BUILD" -maxdepth 1 -type f -name 'gfyms-surface-*.pkg.tar.zst' -print -quit)
test -n "$GFYMS_PKG"
install -Dm644 "$GFYMS_PKG" "$OUTPUT_ROOT/$(basename "$GFYMS_PKG")"

echo '== Prepare ArchISO profile from stock releng ==' 
cp -a /usr/share/archiso/configs/releng "$PROFILE"
sed -i -e "s/^iso_name=.*/iso_name=\"gfyms-surface-pro-7\"/" -e "s/^iso_application=.*/iso_application=\"GFYMS Surface Pro 7 Arch Linux\"/" -e "s/^iso_version=.*/iso_version=\"$VERSION\"/" "$PROFILE/profiledef.sh"

bsdtar -xf "$GFYMS_PKG" -C "$PROFILE/airootfs"
cat "$SOURCE_ROOT/profiles/archiso-surface-pro-7/packages.x86_64" >> "$PROFILE/packages.x86_64"

cat "$PROFILE/pacman.conf" > "$PROFILE/pacman.conf.new"
cat >> "$PROFILE/pacman.conf.new" <<'EOF'

[gfyms-surface-build]
SigLevel = Optional
Server = file:///tmp/gfyms-localrepo
EOF
mv "$PROFILE/pacman.conf.new" "$PROFILE/pacman.conf"

while IFS= read -r -d '' bootcfg; do sed -i -e 's/vmlinuz-linux/vmlinuz-linux-surface/g' -e 's/initramfs-linux/initramfs-linux-surface/g' "$bootcfg"; done < <(grep -rlZ -E 'vmlinuz-linux|initramfs-linux' "$PROFILE" 2>/dev/null || true)

mkdir -p "$PROFILE/airootfs/etc/systemd/system/multi-user.target.wants"
ln -sf /usr/lib/systemd/system/iptsd.service "$PROFILE/airootfs/etc/systemd/system/multi-user.target.wants/iptsd.service"
ln -sf /usr/lib/systemd/system/gfyms-surface.service "$PROFILE/airootfs/etc/systemd/system/multi-user.target.wants/gfyms-surface.service"
ln -sf /usr/lib/systemd/system/NetworkManager.service "$PROFILE/airootfs/etc/systemd/system/multi-user.target.wants/NetworkManager.service"

mkdir -p "$PROFILE/airootfs/usr/share/gfyms"
install -Dm644 "$SOURCE_ROOT/GFYMS_concept_logo-removebg-preview.png" "$PROFILE/airootfs/usr/share/gfyms/gfyms-logo.png"
printf '%s\n' "$VERSION" > "$PROFILE/airootfs/usr/share/gfyms/version"

echo '== Build GFYMS ISO ==' 
mkarchiso -v -r -w "$WORK" -o "$OUTPUT_ROOT" "$PROFILE"
ISO=$(find "$OUTPUT_ROOT" -maxdepth 1 -type f -name '*.iso' -print -quit)
test -s "$ISO"
mv "$ISO" "$OUTPUT_ROOT/gfyms-surface-pro-7-${VERSION}-x86_64.iso"

echo '== Package release tools ==' 
chmod 755 "$SOURCE_ROOT/tools/gfyms-patcher/gfyms-patch" "$SOURCE_ROOT/tools/gfyms-usb/gfyms-usb"
tar -C "$SOURCE_ROOT/tools/gfyms-patcher" -czf "$OUTPUT_ROOT/gfyms-arch-patcher-${VERSION}.tar.gz" gfyms-patch README.md
tar -C "$SOURCE_ROOT/tools/gfyms-usb" -czf "$OUTPUT_ROOT/gfyms-usb-tool-${VERSION}.tar.gz" gfyms-usb README.md

echo '== Release checks ==' 
test -s "$OUTPUT_ROOT/gfyms-surface-pro-7-${VERSION}-x86_64.iso"
test -s "$OUTPUT_ROOT/gfyms-arch-patcher-${VERSION}.tar.gz"
test -s "$OUTPUT_ROOT/gfyms-usb-tool-${VERSION}.tar.gz"
(cd "$OUTPUT_ROOT" && sha256sum ./* > SHA256SUMS)
sha256sum -c "$OUTPUT_ROOT/SHA256SUMS"
echo '== Final artifacts ==' 
ls -lh "$OUTPUT_ROOT"
