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
if ! grep -q '^\[multilib\]$' /etc/pacman.conf; then
  printf '%s\n' '' '[multilib]' 'Include = /etc/pacman.d/mirrorlist' >> /etc/pacman.conf
fi
pacman -Sy --noconfirm
pacman -S --noconfirm --needed base-devel archiso cmake extra-cmake-modules qt6-base qt6-declarative qt6-tools kcmutils kirigami git xorriso curl pciutils usbutils bash coreutils sudo kwin vulkan-headers python python-cryptography alsa-ucm-conf wine wine-mono wine-gecko winetricks cabextract 7zip

echo '== Configure linux-surface signing key ==' 
pacman-key --init
curl -fsSL https://raw.githubusercontent.com/linux-surface/linux-surface/master/pkg/keys/surface.asc | pacman-key --add -
pacman-key --finger 56C464BAAC421453
pacman-key --lsign-key 56C464BAAC421453
if ! grep -q '^\[linux-surface\]$' /etc/pacman.conf; then
  printf '%s\n' '' '[linux-surface]' 'Server = https://pkg.surfacelinux.com/arch/' >> /etc/pacman.conf
fi
pacman -Sy --noconfirm
pacman -Sw --noconfirm linux-surface iptsd

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

echo '== Configure GFYMS custom build repository ==' 
LOCAL_REPO=/tmp/gfyms-repo
rm -rf "$LOCAL_REPO"
mkdir -p "$LOCAL_REPO"
cp /var/cache/pacman/pkg/linux-surface-*.pkg.tar.zst "$LOCAL_REPO/"
cp /var/cache/pacman/pkg/iptsd-*.pkg.tar.zst "$LOCAL_REPO/"
cp "$OUTPUT_ROOT"/gfyms-surface-[0-9]*.pkg.tar.zst "$LOCAL_REPO/"
cp "$OUTPUT_ROOT"/gfyms-findmy-[0-9]*.pkg.tar.zst "$LOCAL_REPO/"
cp "$OUTPUT_ROOT"/gfyms-rounded-corners-[0-9]*.pkg.tar.zst "$LOCAL_REPO/"
repo-add "$LOCAL_REPO/custom.db.tar.zst" "$LOCAL_REPO"/*.pkg.tar.zst

if ! grep -q '^\[multilib\]$' "$PROFILE/pacman.conf"; then
  printf '%s\n' '' '[multilib]' 'Include = /etc/pacman.d/mirrorlist' >> "$PROFILE/pacman.conf"
fi

awk '
  BEGIN { added=0 }
  /^\[core\]$/ && !added {
    print "[custom]"
    print "SigLevel = Optional TrustAll"
    print "Server = file:///tmp/gfyms-repo"
    print ""
    added=1
  }
  { print }
' "$PROFILE/pacman.conf" > "$PROFILE/pacman.conf.new"
mv "$PROFILE/pacman.conf.new" "$PROFILE/pacman.conf"

echo '== Select runtime package set for ArchISO ==' 
sed -i '/^linux$/d;/^linux-surface-headers$/d' "$PROFILE/packages.x86_64"
sed '/^linux-surface-headers$/d' "$SOURCE_ROOT/profiles/archiso-surface-pro-7/packages.x86_64" >> "$PROFILE/packages.x86_64"

echo '== Configure ArchISO live environment ==' 
mkdir -p "$PROFILE/airootfs/root"
cat > "$PROFILE/airootfs/root/customize_airootfs.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if ! id gfyms >/dev/null 2>&1; then
  useradd -m -G wheel -s /bin/bash gfyms
fi
passwd -d gfyms >/dev/null 2>&1 || true

systemctl enable NetworkManager.service
systemctl enable sddm.service
systemctl enable iptsd.service || true
systemctl enable gfyms-surface.service || true
systemctl enable gfyms-findmy.service || true
systemctl enable gfyms-auto-update.timer || true

install -d -m 0755 /etc/sddm.conf.d
cat > /etc/sddm.conf.d/10-gfyms.conf <<'EOT'
[Autologin]
User=gfyms
Session=plasmawayland
Relogin=false
EOT
EOF
chmod 755 "$PROFILE/airootfs/root/customize_airootfs.sh"
echo '== Point ArchISO boot entries at the Surface kernel ==' 
while IFS= read -r -d '' bootcfg; do
  sed -i -e 's/vmlinuz-linux-surface-surface/vmlinuz-linux-surface/g' -e 's/vmlinuz-linux/vmlinuz-linux-surface/g' -e 's/initramfs-linux-surface-surface/initramfs-linux-surface/g' -e 's/initramfs-linux/initramfs-linux-surface/g' "$bootcfg"
done < <(grep -rlZ -E 'vmlinuz-linux|initramfs-linux' "$PROFILE" 2>/dev/null || true)

echo '== Install GFYMS logo/version/FastFetch into image ==' 
mkdir -p "$PROFILE/airootfs/usr/share/gfyms"
install -Dm644 "$SOURCE_ROOT/GFYMS_concept_logo-removebg-preview.png" "$PROFILE/airootfs/usr/share/gfyms/gfyms-logo.png"
printf '%s\n' "$VERSION" > "$PROFILE/airootfs/usr/share/gfyms/version"

install -Dm644 "$SOURCE_ROOT/profiles/archiso-surface-pro-7/fastfetch/gfyms-logo.txt" \
  "$PROFILE/airootfs/usr/share/gfyms/fastfetch-logo.txt"
install -Dm644 "$SOURCE_ROOT/profiles/archiso-surface-pro-7/fastfetch/config.jsonc" \
  "$PROFILE/airootfs/etc/skel/.config/fastfetch/config.jsonc"

cat >> "$PROFILE/airootfs/etc/skel/.bashrc" <<'EOF'

# GFYMS FastFetch
if [[ $- == *i* ]] && command -v fastfetch >/dev/null 2>&1; then
  fastfetch
fi
EOF

echo '== Build GFYMS ISO ==' 
mkarchiso -v -r -w "$WORK" -o "$OUTPUT_ROOT" "$PROFILE"
ISO=$(find "$OUTPUT_ROOT" -maxdepth 1 -type f -name '*.iso' -print -quit)
test -s "$ISO"

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
(cd "$OUTPUT_ROOT" && sha256sum ./* > SHA256SUMS && sha256sum -c SHA256SUMS)

echo '== Final artifacts ==' 
ls -lh "$OUTPUT_ROOT"
