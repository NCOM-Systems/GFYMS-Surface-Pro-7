#!/usr/bin/env bash
set -euo pipefail

: "${VERSION:?VERSION must be supplied}"
: "${SOURCE_ROOT:=/src}"
: "${OUTPUT_ROOT:=/src/release-build}"

PROFILE=/tmp/gfyms-profile
WORK=/tmp/gfyms-work
PKG_BUILD=/tmp/build

rm -rf "$PROFILE" "$WORK" "$PKG_BUILD" "$OUTPUT_ROOT"
mkdir -p "$OUTPUT_ROOT"

echo '== Bootstrap Arch build environment ==' 
pacman -Syu --noconfirm
pacman -S --noconfirm --needed base-devel archiso cmake extra-cmake-modules qt6-base qt6-declarative qt6-tools kcmutils kirigami git xorriso curl pciutils usbutils bash coreutils sudo kwin vulkan-headers python python-cryptography

echo '== Configure linux-surface signing key ==' 
pacman-key --init
curl -fsSL https://raw.githubusercontent.com/linux-surface/linux-surface/master/pkg/keys/surface.asc | pacman-key --add -
pacman-key --finger 56C464BAAC421453
pacman-key --lsign-key 56C464BAAC421453
if ! grep -q '^\[linux-surface\]$' /etc/pacman.conf; then
  printf '%s\n' '' '[linux-surface]' 'Server = https://pkg.surfacelinux.com/arch/' >> /etc/pacman.conf
fi
pacman -Sy --noconfirm
pacman -Sw --noconfirm linux-surface linux-surface-headers iptsd

echo '== Create unprivileged Arch package builder ==' 
useradd -m -U builder
printf '%s\n' 'builder ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/gfyms-builder
chmod 440 /etc/sudoers.d/gfyms-builder

build_pkg() {
  local name="$1"
  local src="$SOURCE_ROOT/packages/$name"
  local work="$PKG_BUILD/$name"
  rm -rf "$work"
  mkdir -p "$work"
  cp -a "$src"/. "$work/"
  if [[ "$name" == 'gfyms-surface' ]]; then
    cp "$SOURCE_ROOT/GFYMS_concept_logo-removebg-preview.png" "$work/gfyms-logo.png"
  fi
  chown -R builder:builder "$work"
  su - builder -c "cd '$work' && makepkg --syncdeps --noconfirm --clean --cleanbuild"
  local pkg
  pkg=$(find "$work" -maxdepth 1 -type f -name "$name-[0-9]*.pkg.tar.zst" -print -quit)
  test -n "$pkg"
  install -Dm644 "$pkg" "$OUTPUT_ROOT/$(basename "$pkg")"
}

echo '== Build GFYMS native packages ==' 
build_pkg gfyms-surface
build_pkg gfyms-findmy
build_pkg gfyms-rounded-corners

echo '== Prepare stock ArchISO releng profile ==' 
cp -a /usr/share/archiso/configs/releng "$PROFILE"
sed -i -e "s/^iso_name=.*/iso_name=\"gfyms-surface-pro-7\"/" -e "s/^iso_application=.*/iso_application=\"GFYMS Surface Pro 7 Arch Linux\"/" -e "s/^iso_version=.*/iso_version=\"$VERSION\"/" "$PROFILE/profiledef.sh"

echo '== Remove externally resolved Surface packages from package list ==' 
sed -i '/^gfyms-surface$/d;/^gfyms-findmy$/d;/^gfyms-rounded-corners$/d;/^linux-surface$/d;/^linux-surface-headers$/d;/^iptsd$/d' "$PROFILE/packages.x86_64"
# Keep the stock linux package available for the initial ArchISO build; it is
# replaced by linux-surface in customize_airootfs.sh below.
cat "$SOURCE_ROOT/profiles/archiso-surface-pro-7/packages.x86_64" | sed '/^gfyms-surface$/d;/^gfyms-findmy$/d;/^gfyms-rounded-corners$/d;/^linux-surface$/d;/^linux-surface-headers$/d;/^iptsd$/d' >> "$PROFILE/packages.x86_64"

echo '== Stage verified packages inside the image ==' 
mkdir -p "$PROFILE/airootfs/root/gfyms-packages"
cp /var/cache/pacman/pkg/linux-surface-*.pkg.tar.zst "$PROFILE/airootfs/root/gfyms-packages/"
cp /var/cache/pacman/pkg/linux-surface-headers-*.pkg.tar.zst "$PROFILE/airootfs/root/gfyms-packages/"
cp /var/cache/pacman/pkg/iptsd-*.pkg.tar.zst "$PROFILE/airootfs/root/gfyms-packages/"
cp "$OUTPUT_ROOT"/gfyms-*.pkg.tar.zst "$PROFILE/airootfs/root/gfyms-packages/"

echo '== Configure ArchISO live environment ==' 
mkdir -p "$PROFILE/airootfs/root"
cat > "$PROFILE/airootfs/root/customize_airootfs.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

echo 'GFYMS: installing verified Surface/GFYMS package set'
pacman -U --noconfirm --needed /root/gfyms-packages/*.pkg.tar.zst
pacman -Rns --noconfirm linux || true

if ! id gfyms >/dev/null 2>&1; then
  useradd -m -G wheel -s /bin/bash gfyms
fi
passwd -d gfyms >/dev/null 2>&1 || true

systemctl enable NetworkManager.service
systemctl enable sddm.service
systemctl enable iptsd.service || true
systemctl enable gfyms-surface.service || true
systemctl enable gfyms-auto-update.timer || true

install -d -m 0755 /etc/sddm.conf.d
cat > /etc/sddm.conf.d/10-gfyms.conf <<'EOT'
[Autologin]
User=gfyms
Session=plasmawayland
Relogin=false
EOT

rm -rf /root/gfyms-packages
EOF
chmod 755 "$PROFILE/airootfs/root/customize_airootfs.sh"

echo '== Point ArchISO boot entries at the Surface kernel ==' 
while IFS= read -r -d '' bootcfg; do
  sed -i -e 's/vmlinuz-linux-surface-surface/vmlinuz-linux-surface/g' -e 's/vmlinuz-linux/vmlinuz-linux-surface/g' -e 's/initramfs-linux-surface-surface/initramfs-linux-surface/g' -e 's/initramfs-linux/initramfs-linux-surface/g' "$bootcfg"
done < <(grep -rlZ -E 'vmlinuz-linux|initramfs-linux' "$PROFILE" 2>/dev/null || true)

echo '== Install GFYMS logo/version into image ==' 
mkdir -p "$PROFILE/airootfs/usr/share/gfyms"
install -Dm644 "$SOURCE_ROOT/GFYMS_concept_logo-removebg-preview.png" "$PROFILE/airootfs/usr/share/gfyms/gfyms-logo.png"
printf '%s\n' "$VERSION" > "$PROFILE/airootfs/usr/share/gfyms/version"

echo '== Build GFYMS ISO ==' 
mkarchiso -v -r -w "$WORK" -o "$OUTPUT_ROOT" "$PROFILE"
ISO=$(find "$OUTPUT_ROOT" -maxdepth 1 -type f -name '*.iso' -print -quit)
test -s "$ISO"
mv "$ISO" "$OUTPUT_ROOT/gfyms-surface-pro-7-${VERSION}-x86_64.iso"

echo '== Package patcher and USB tool ==' 
chmod 755 "$SOURCE_ROOT/tools/gfyms-patcher/gfyms-patch" "$SOURCE_ROOT/tools/gfyms-usb/gfyms-usb"
tar -C "$SOURCE_ROOT/tools/gfyms-patcher" -czf "$OUTPUT_ROOT/gfyms-arch-patcher-${VERSION}.tar.gz" gfyms-patch README.md
tar -C "$SOURCE_ROOT/tools/gfyms-usb" -czf "$OUTPUT_ROOT/gfyms-usb-tool-${VERSION}.tar.gz" gfyms-usb README.md

echo '== Release manifest ==' 
python - <<'PY'
import hashlib
import json
import pathlib
import os

root = pathlib.Path('/src/release-build')
version = os.environ['VERSION']
packages = sorted(root.glob('gfyms-*.pkg.tar.zst'))
manifest = {
    'schema': 1,
    'version': version,
    'channel': 'preview' if any(x in version for x in ('preview', 'alpha', 'beta')) else 'stable',
    'packages': [{'name': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in packages],
    'artifacts': {
        'iso': f'gfyms-surface-pro-7-{version}-x86_64.iso',
        'patcher': f'gfyms-arch-patcher-{version}.tar.gz',
        'usb_tool': f'gfyms-usb-tool-{version}.tar.gz'
    }
}
(root / 'GFYMS-MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
PY

echo '== Release checks ==' 
SURFACE_RELEASE_PKG=$(find "$OUTPUT_ROOT" -maxdepth 1 -type f -name 'gfyms-surface-[0-9]*.pkg.tar.zst' -print -quit)
test -s "$SURFACE_RELEASE_PKG"
test -s "$(find "$OUTPUT_ROOT" -maxdepth 1 -name 'gfyms-findmy-*.pkg.tar.zst' -print -quit)"
test -s "$(find "$OUTPUT_ROOT" -maxdepth 1 -name 'gfyms-rounded-corners-*.pkg.tar.zst' -print -quit)"
test -s "$OUTPUT_ROOT/gfyms-surface-pro-7-${VERSION}-x86_64.iso"
test -s "$OUTPUT_ROOT/gfyms-arch-patcher-${VERSION}.tar.gz"
test -s "$OUTPUT_ROOT/gfyms-usb-tool-${VERSION}.tar.gz"
(cd "$OUTPUT_ROOT" && sha256sum ./* > SHA256SUMS)
sha256sum -c "$OUTPUT_ROOT/SHA256SUMS"

echo '== Final artifacts ==' 
ls -lh "$OUTPUT_ROOT"
