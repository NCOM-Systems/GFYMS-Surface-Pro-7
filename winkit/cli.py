from __future__ import annotations

import argparse
from pathlib import Path

from .runner import apply_manifest, load_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="WinKIT manifest-gated runner")
    parser.add_argument("manifest", type=Path, help="path to WinKIT JSON manifest")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="manifest-relative artifact root",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="allow mutation after inspection and verification",
    )
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    for line in apply_manifest(manifest, root=args.root, apply=args.apply):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
