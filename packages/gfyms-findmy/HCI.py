#!/usr/bin/env python3

import base64
import subprocess
import time
import struct
import argparse
import sys

def advertisement_template():
    adv = ""
    adv += "1e"
    adv += "ff"
    adv += "4c00"
    adv += "1219"
    adv += "00"
    for _ in range(22):
        adv += "00"
    adv += "00"
    adv += "00"
    return bytearray.fromhex(adv)

def bytes_to_strarray(bytes_, with_prefix=False):
    if with_prefix:
        return [hex(b) for b in bytes_]
    return [format(b, "x") for b in bytes_]

def run_hci_cmd(cmd, hci="hci0", wait=1):
    cmd_ = ["hcitool", "-i", hci, "cmd"]
    cmd_ += cmd
    print(cmd_)
    subprocess.run(cmd_, check=True)
    if wait > 0:
        time.sleep(wait)

def start_advertising(key, interval_ms=2000):
    if len(key) != 28:
        raise ValueError("Advertisement key must be exactly 28 bytes.")
    addr = bytearray(key[:6])
    addr[0] |= 0b11000000
    adv = advertisement_template()
    adv[7:29] = key[6:28]
    adv[29] = key[0] >> 6
    run_hci_cmd(["0x3f", "0x001"] + bytes_to_strarray(addr, with_prefix=True)[::-1])
    subprocess.run(["systemctl", "restart", "bluetooth"], check=True)
    time.sleep(1)
    run_hci_cmd(["0x08", "0x0008"] + [format(len(adv), "x")] + bytes_to_strarray(adv))
    interval_enc = struct.pack("<h", interval_ms)
    hci_set_adv_params = ["0x08", "0x0006"]
    hci_set_adv_params += bytes_to_strarray(interval_enc)
    hci_set_adv_params += bytes_to_strarray(interval_enc)
    hci_set_adv_params += ["03", "00", "00", "00", "00", "00", "00", "00", "00"]
    hci_set_adv_params += ["07", "00"]
    run_hci_cmd(hci_set_adv_params)
    run_hci_cmd(["0x08", "0x000a", "01"], wait=0)

def main(args):
    parser = argparse.ArgumentParser()
    parser.add_argument("--key", "-k", required=True, help="Advertisement key (base64)")
    parser.add_argument("--hci", default="hci0", help="Bluetooth HCI device")
    args = parser.parse_args(args)
    key = base64.b64decode(args.key.encode())
    start_advertising(key)

if __name__ == "__main__":
    main(sys.argv[1:])