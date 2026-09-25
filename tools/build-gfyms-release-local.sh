#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(cat "$ROOT/VERSION")"
OUTPUT="$ROOT/release-build"

command -v docker >/dev/null 2>&1 || {
  echo "Docker is required. Install the docker package and enable docker.service." >&2
  exit 1
}

mkdir -p "$OUTPUT"
echo "Building GFYMS Surface Pro 7 ISO ${VERSION}"
docker run --rm --privileged   -e VERSION="$VERSION"   -e SOURCE_ROOT=/src   -e OUTPUT_ROOT=/out   -v "$ROOT:/src:ro"   -v "$OUTPUT:/out"   -w /src   archlinux:latest   /src/tools/build-gfyms-release.sh

echo "== Local build complete =="
ls -lh "$OUTPUT"
echo "Verify: (cd \"$OUTPUT\" && sha256sum -c SHA256SUMS)"
