# GFYMS Surface Pen: low-latency and precision plan

## Scope and honest target

The goal is the fastest, most stable and most accurate Surface Pro 7 pen path the hardware can deliver. The target experience is **Apple-Pencil-like in responsiveness and fluidity where the SP7 digitizer, pen and display hardware allow it**. We must not promise Apple Pencil Pro equivalence until the same physical pen, digitizer and display path are measured against a defined test fixture.

The first task is not to add a larger smoothing filter. It is to measure and remove avoidable latency, packet loss, coordinate error, bad pressure mapping, compositor queueing and palm-rejection stalls.

## Architecture decision

KDE Plasma Wayland is an output and presentation endpoint, not the primary stylus implementation. GFYMS must own the path from the Surface digitizer to a normalized tablet event stream:

```text
Surface digitizer / IPTS / HID reports
        |
        v
GFYMS pen capture backend
  - timestamp preservation
  - report decoding
  - packet loss detection
  - tool/proximity state
  - calibration and coordinate transform
        |
        v
GFYMS pen signal engine
  - pressure curve
  - adaptive denoise
  - palm rejection state machine
  - bounded prediction
  - tilt/azimuth normalization
  - resampling to display clock
        |
        +--> diagnostic trace and replay file
        +--> Linux evdev/uinput tablet device
        +--> optional GFYMS D-Bus control API
        |
        v
KWin/Wayland tablet protocol and applications
```

The GFYMS engine must work without KDE. KDE/libinput may consume the resulting standard tablet events, but it must not be the only place where pressure curves, filtering, calibration or latency policy exists.

## What can actually improve latency

### Capture and scheduling

- Preserve device-provided scan time when available; do not replace it with delayed userspace receipt time.
- Emit one complete event packet per hardware report and never wait for an arbitrary timer to batch pen packets.
- Use `SYN_REPORT` packet boundaries correctly.
- Detect `SYN_DROPPED` and recover state instead of drawing stale or discontinuous points.
- Use a dedicated real-time-capable worker only after measuring scheduler delay; prefer bounded `SCHED_FIFO`/`SCHED_RR` policy with a safe fallback, not an unconditional system-wide real-time change.
- Pin only the capture worker if profiling proves migration is harmful. Do not pin the entire desktop or disable thermal controls.
- Keep the pen thread allocation-free in the hot path and use a lock-free or bounded single-producer/single-consumer queue.
- Use monotonic timestamps throughout the pipeline.

### Signal processing

- Start with zero added smoothing and establish raw accuracy and jitter.
- Use a pressure dead-zone and a configurable response curve, not a large moving average.
- Use adaptive filtering: stronger only when stationary/hovering, weaker during fast strokes.
- Use velocity-aware prediction for display alignment, with a strict prediction horizon and automatic reset on direction changes, pen-up, proximity changes or packet gaps.
- Never let prediction alter persisted ink data without an application's explicit policy. Prediction is for presentation; raw and corrected traces must remain available for replay and testing.
- Resample only to the display frame deadline. Do not invent extra samples when the hardware is late.
- Preserve 16-bit-or-better coordinate precision internally until the final output boundary.

### Coordinate and pressure quality

- Obtain the actual digitizer X/Y ranges from sysfs/evdev and calibrate against the panel's active display geometry.
- Correct rotation, scale, offset and aspect ratio in one place.
- Validate that pen and touch coordinates use the same physical panel transform.
- Expose pressure, tip, in-range, barrel button, eraser, tilt and tool identity independently.
- Store per-pen calibration by transducer identity when the hardware provides one; otherwise use a device profile, not a guessed serial number.
- Make pressure curves reversible and versioned.

### Palm rejection

Palm rejection must be a state machine, not a global touch-off switch:

1. Detect pen proximity and pen contact.
2. Apply a short, measured arbitration window for contacts near the pen.
3. Suppress or downgrade only contacts classified as palm candidates.
4. Preserve intentional finger gestures away from the pen.
5. Release suppression immediately and safely on pen-up or timeout.
6. Record decisions in a debug trace so false positives can be diagnosed.

The policy must never silently disable the entire touchscreen or make the device unusable when the pen is absent.

## Hardware boundaries

No userspace filter can overcome a slow digitizer scan rate, a delayed IPTS transport, Bluetooth pen latency, display scanout delay, or a compositor frame deadline. We must separately measure:

- digitizer report interval and jitter;
- kernel interrupt-to-evdev delay;
- GFYMS capture-to-output delay;
- compositor input-to-frame delay;
- display scanout and visible-stroke delay;
- pressure and coordinate error;
- dropped reports during CPU, thermal and suspend/resume stress.

The Windows extracted corpus is evidence for report layouts, firmware relationships and configuration clues. Microsoft pen binaries are not the runtime implementation. The native GFYMS backend must be independently implemented and must not ship proprietary `.sys`, `.dll` or firmware files without a documented license and distribution basis.

## Required test fixtures

### Automated replay

Capture raw legal test traces containing pen-down, hover, slow diagonal, fast diagonal, circles, pressure ramps, tilt sweeps, barrel-button transitions, pen-up, palm contact, packet gaps and suspend/resume boundaries. Replay them deterministically through the signal engine and compare:

- no packet reordering;
- no coordinate overshoot above the configured prediction horizon;
- pressure monotonicity during ramps;
- no false tip-down during hover;
- bounded output jitter;
- exact reset behavior after gaps and tool changes.

### Physical hardware

Use a fixed Surface Pro 7 test protocol with a marked calibration sheet, high-speed camera or photodiode-style visual timing method where possible, and repeated runs at cold, warm, battery and AC power states. Report median, p95 and worst-case values, not only a subjective “feels smooth.”

### Application matrix

Validate at least Xournal++, Krita, KDE's tablet test path, browser canvas input, Android native runtime input, and a raw evdev/libinput monitor. A pass in one application does not prove the full pipeline.

## Planned GFYMS components

- `packages/gfyms-surface-pen/` — native package, configuration, service and diagnostics
- `gfyms-pen-capture` — read-only capture/decoder with raw trace mode
- `gfyms-pen-engine` — deterministic pressure/filter/prediction/palm engine
- `gfyms-pen-replay` — offline regression runner
- `gfyms-penctl` — inspect, calibrate, profile, trace and reset commands
- `gfyms-pen.service` — optional user service, never required for boot
- GFYMS Center pen page — controls backed by the real engine, not only stored UI preferences

## Tuning profiles

Profiles should be explicit and reversible:

- `accurate` — no prediction, minimal filtering, rawest trace
- `balanced` — bounded adaptive filtering and short display prediction
- `fast-stroke` — shortest safe prediction horizon with aggressive gap reset
- `ink` — pressure curve and palm rejection tuned for writing
- `drawing` — low smoothing and full tilt/pressure resolution
- `diagnostic` — raw capture plus timestamps, no signal modification

The default must be `balanced` only after physical testing. Before that, default to `accurate` and expose a diagnostic report.

## Sources

- Linux input event packets, `SYN_REPORT`, `SYN_DROPPED`, tool codes and optional `MSC_TIMESTAMP`: https://docs.kernel.org/input/event-codes.html
- libinput tablet semantics for pressure, tilt, proximity and calibration: https://wayland.freedesktop.org/libinput/doc/latest/tablet-support.html
- Microsoft integrated pen HID usages, scan time and latency-mode feature guidance: https://learn.microsoft.com/en-us/windows-hardware/design/component-guidelines/required-hid-top-level-collections
- Existing GFYMS pen UI contract: https://github.com/NCOM-Systems/GFYMS-Surface-Pro-7/blob/main/docs/GFYMS-PEN-CENTER.md
- Linux Surface Pro 7 discussion documenting large Linux pen lag and the need for a native low-latency path: https://github.com/linux-surface/linux-surface/discussions/593
