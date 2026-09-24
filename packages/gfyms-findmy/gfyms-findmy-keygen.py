#!/usr/bin/env python3

import argparse
import base64
import hashlib
import json
import pathlib
from cryptography.hazmat.primitives.asymmetric import ec

def main() -> None:
    parser = argparse.ArgumentParser(description="Create an OpenHaystack-compatible P-224 key set.")
    parser.add_argument("name", help="Device name")
    parser.add_argument("-o", "--output", default=".", help="Output directory")
    args = parser.parse_args()
    private_key = ec.generate_private_key(ec.SECP224R1())
    private_bytes = private_key.private_numbers().private_value.to_bytes(28, "big")
    advertised = private_key.public_key().public_numbers().x.to_bytes(28, "big")
    hashed = hashlib.sha256(advertised).digest()
    out = pathlib.Path(args.output).expanduser().resolve() / args.name
    out.mkdir(parents=True, exist_ok=False)
    (out / "private.key").write_text(base64.b64encode(private_bytes).decode("ascii") + "\n", encoding="ascii")
    (out / "advertisement.key").write_text(base64.b64encode(advertised).decode("ascii") + "\n", encoding="ascii")
    (out / "advertisement.sha256").write_text(base64.b64encode(hashed).decode("ascii") + "\n", encoding="ascii")
    metadata = {"name": args.name, "curve": "secp224r1", "advertisement_key_base64": base64.b64encode(advertised).decode("ascii"), "advertisement_key_sha256_base64": base64.b64encode(hashed).decode("ascii")}
    (out / "device.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(out)
    print("Keep private.key secret.")

if __name__ == "__main__":
    main()