# GFYMS Find My Bridge

GFYMS exposes an optional OpenHaystack-compatible BLE beacon service.

OpenHaystack documents a Linux HCI path and says Linux machines can be used as beacons. GFYMS wraps that concept as an optional Surface service.

## Important distinction

This is not Apple-certified registration of the Surface as an official Find My product. Apple controls the Find My network, and OpenHaystack is experimental and unaffiliated with Apple.

## Setup model

Store a user-owned OpenHaystack advertisement key at:

/var/lib/gfyms/findmy/advertisement.key

Then enable the beacon from GFYMS Center.

The beacon needs working Bluetooth LE advertising. Suspend, airplane mode, Bluetooth power management, firmware and BlueZ behavior can interrupt availability.

Location retrieval is separate from beacon transmission. Community Linux projects such as FindMy can query Find My reports with Apple-authenticated tooling, but Apple does not expose the service as a public GFYMS API.
