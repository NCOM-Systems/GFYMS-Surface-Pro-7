#!/usr/bin/env python3
import argparse
import base64
import subprocess
import time

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--key-file", required=True)
    parser.add_argument("--hci", default="hci0")
    args = parser.parse_args()

    with open(args.key_file, "rb") as handle:
        key = base64.b64decode(handle.read().strip())

    if len(key) < 28:
        raise SystemExit("Advertisement key must decode to at least 28 bytes.")

    key = key[:28]
    address = bytearray(key[:6])
    address[0] |= 0xC0

    advertisement = bytearray.fromhex("1eff4c00121900" + ("00" * 22) + "00")
    advertisement[7:29] = key[6:28]
    advertisement[29] = key[0] >> 6

    def hci(*parts: str) -> None:
        subprocess.run(["hcitool", "-i", args.hci, "cmd", *parts], check=True)

    hci("0x3f", "0x001", *[f"0x{x:02x}" for x in reversed(address)])
    subprocess.run(["systemctl", "restart", "bluetooth"], check=True)
    time.sleep(1)
    hci("0x08", "0x0008", "0x1e", *[f"0x{x:02x}" for x in advertisement])

    interval = (2000).to_bytes(2, "little")
    params = ["0x08", "0x0006"]
    params += [f"0x{x:02x}" for x in interval]
    params += [f"0x{x:02x}" for x in interval]
    params += ["03", "00", "00", "00", "00", "00", "00", "00", "00", "07", "00"]
    hci(*params)
    hci("0x08", "0x000a", "01")

if __name__ == "__main__":
    main()
