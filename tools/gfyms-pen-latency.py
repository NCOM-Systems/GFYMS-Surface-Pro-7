#!/usr/bin/env python3
"""Measure Linux pen event timing without modifying the device or system policy.

This reports source packet intervals and an approximate userspace queue delay.
It is not an end-to-end visible latency measurement; display/compositor delay
requires a separate hardware test fixture.
"""
from __future__ import annotations

import argparse
import os
import struct
import statistics
import time
from pathlib import Path

EVENT = struct.Struct("llHHI")
EV_SYN = 0
SYN_REPORT = 0
SYN_DROPPED = 3
EV_KEY = 1
EV_ABS = 3
BTN_TOOL_PEN = 320
BTN_TOUCH = 330


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * fraction))
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("device", type=Path, help="read-only /dev/input/eventX node")
    parser.add_argument("--seconds", type=float, default=10.0)
    args = parser.parse_args()
    if args.seconds <= 0:
        parser.error("--seconds must be positive")

    intervals: list[float] = []
    queue_delays: list[float] = []
    packets = 0
    dropped = 0
    pen_events = 0
    touch_events = 0
    previous_source_ns: int | None = None
    deadline = time.monotonic() + args.seconds

    # O_RDONLY|O_NONBLOCK avoids writes and prevents a hung device from blocking
    # diagnostics indefinitely. The kernel input ABI supplies timeval seconds/usec.
    fd = os.open(args.device, os.O_RDONLY | os.O_NONBLOCK)
    try:
        while time.monotonic() < deadline:
            try:
                data = os.read(fd, EVENT.size * 64)
            except BlockingIOError:
                time.sleep(0.0005)
                continue
            if not data:
                break
            receipt_wall_ns = time.time_ns()
            for offset in range(0, len(data) - EVENT.size + 1, EVENT.size):
                sec, usec, event_type, code, value = EVENT.unpack_from(data, offset)
                source_ns = sec * 1_000_000_000 + usec * 1_000
                if event_type == EV_KEY and code == BTN_TOOL_PEN:
                    pen_events += 1
                elif event_type == EV_KEY and code == BTN_TOUCH:
                    touch_events += 1
                elif event_type == EV_SYN and code == SYN_DROPPED:
                    dropped += 1
                elif event_type == EV_SYN and code == SYN_REPORT:
                    packets += 1
                    if previous_source_ns is not None:
                        intervals.append((source_ns - previous_source_ns) / 1_000_000.0)
                    previous_source_ns = source_ns
                    delay_ms = (receipt_wall_ns - source_ns) / 1_000_000.0
                    # Clock domains normally match for evdev timeval on Linux;
                    # reject impossible values rather than publishing nonsense.
                    if 0.0 <= delay_ms < 10_000.0:
                        queue_delays.append(delay_ms)
    finally:
        os.close(fd)

    print(f"device={args.device}")
    print(f"duration_s={args.seconds:.3f}")
    print(f"packets={packets} dropped={dropped} pen_key_events={pen_events} touch_key_events={touch_events}")
    if intervals:
        print("packet_interval_ms="
              f"mean:{statistics.mean(intervals):.3f} "
              f"p50:{percentile(intervals, .50):.3f} "
              f"p95:{percentile(intervals, .95):.3f} "
              f"max:{max(intervals):.3f}")
    else:
        print("packet_interval_ms=insufficient-data")
    if queue_delays:
        print("approx_queue_delay_ms="
              f"mean:{statistics.mean(queue_delays):.3f} "
              f"p50:{percentile(queue_delays, .50):.3f} "
              f"p95:{percentile(queue_delays, .95):.3f} "
              f"max:{max(queue_delays):.3f}")
    else:
        print("approx_queue_delay_ms=insufficient-data")
    print("note=end-to-end visible latency requires a display or high-speed-camera fixture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
