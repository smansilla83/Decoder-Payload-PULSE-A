"""
Oscilloscope CSV Payload Decoder
Reads time/voltage CSV data exported from an oscilloscope, extracts a binary
bit stream, and decodes the payload.

Confirmed format (Tektronix):
  iRecord Length,Analog:14000
  Sample Rate,100000000.0
  Vertical Scale,CH1: 1.00
  Vertical Offset,CH1:0.00000
  Horizontal Scale, 0.000100000
  Second,Volt
  -0.000500000,5.000
  ...

Usage:
  python decoder_1.py <file.csv> [options]

Examples:
  python decoder_1.py capture.csv
  python decoder_1.py capture.csv --threshold 2.5 --baud 9600 --encoding ascii
  python decoder_1.py capture.csv --lsb-first --bits 8 --encoding hex
  python decoder_1.py capture.csv --invert          # active-low signal
"""

import sys
import argparse
from pathlib import Path


# ---------------------------------------------------------------------------
# CSV loading — Tektronix format + generic fallback
# ---------------------------------------------------------------------------

KNOWN_META_KEYS = {
    "record length":  "record_length",
    "sample rate":    "sample_rate",
    "vertical scale": "vertical_scale",
    "vertical offset":"vertical_offset",
    "horizontal scale":"horizontal_scale",
}


def parse_csv_content(text: str) -> tuple[dict, list[float], list[float]]:
    """
    Parse oscilloscope CSV text (already read into a string).
    Returns (metadata_dict, times, voltages).
    """
    lines = text.splitlines()
    meta: dict[str, str] = {}
    data_start = 0

    # --- pass 1: collect metadata and find first data row ---
    for i, line in enumerate(lines):
        parts = [p.strip() for p in line.split(",", 1)]
        if len(parts) < 2:
            continue

        key_lower = parts[0].lower()

        matched = False
        for pattern, field in KNOWN_META_KEYS.items():
            if pattern in key_lower:
                meta[field] = parts[1]
                matched = True
                break

        if matched:
            continue

        # Skip column-label rows ("Second,Volt", "TIME,CH1", etc.)
        if not _is_float(parts[0]):
            continue

        data_start = i
        break

    # --- pass 2: detect 2-col vs 3-col layout ---
    sample_parts = [p.strip() for p in lines[data_start].split(",")]
    three_col = (
        len(sample_parts) >= 3
        and _is_float(sample_parts[0])
        and _is_float(sample_parts[1])
        and _is_float(sample_parts[2])
    )

    # --- pass 3: read data ---
    times: list[float] = []
    voltages: list[float] = []

    for line in lines[data_start:]:
        if not line.strip():
            continue
        row = [p.strip() for p in line.split(",")]
        try:
            if three_col:
                t, v = float(row[1]), float(row[2])
            else:
                t, v = float(row[0]), float(row[1])
            times.append(t)
            voltages.append(v)
        except (ValueError, IndexError):
            continue

    if not times:
        raise ValueError("No numeric data found in the CSV file.")

    return meta, times, voltages


def load_csv(path: str) -> tuple[dict, list[float], list[float]]:
    """Load an oscilloscope CSV from disk. Returns (metadata, times, voltages)."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        return parse_csv_content(f.read())


def _is_float(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Threshold & raw bit extraction
# ---------------------------------------------------------------------------

def auto_threshold(voltages: list[float]) -> float:
    """Midpoint between signal high and low levels."""
    return (max(voltages) + min(voltages)) / 2.0


def to_bits(voltages: list[float], threshold: float, invert: bool) -> list[int]:
    """Convert voltage samples to 1/0 using the threshold."""
    bits = [1 if v >= threshold else 0 for v in voltages]
    if invert:
        bits = [1 - b for b in bits]
    return bits


# ---------------------------------------------------------------------------
# Baud-rate detection
# ---------------------------------------------------------------------------

def detect_baud(times: list[float], bits: list[int]) -> float:
    """
    Estimate baud rate from the shortest contiguous run of identical bits.
    Cross-checks against the oscilloscope sample rate when available.
    """
    if len(times) < 2:
        raise ValueError("Not enough samples to estimate baud rate.")

    # Shortest run duration → one bit period
    run_start = 0
    run_val = bits[0]
    min_duration = float("inf")

    for i in range(1, len(bits)):
        if bits[i] != run_val:
            duration = times[i - 1] - times[run_start]
            if duration > 0:
                min_duration = min(min_duration, duration)
            run_start = i
            run_val = bits[i]

    # Last run
    if times[-1] > times[run_start]:
        duration = times[-1] - times[run_start]
        min_duration = min(min_duration, duration)

    if min_duration == float("inf") or min_duration == 0:
        raise ValueError(
            "Could not detect bit period from signal transitions. "
            "Try specifying --baud manually."
        )

    raw_baud = 1.0 / min_duration

    # Snap to nearest standard baud rate if close enough (within 5%)
    STANDARD_BAUDS = [
        300, 600, 1200, 2400, 4800, 9600, 14400, 19200,
        28800, 38400, 57600, 115200, 230400, 460800, 921600,
        1000000, 2000000, 4000000,
    ]
    for std in STANDARD_BAUDS:
        if abs(raw_baud - std) / std < 0.05:
            return float(std)

    return raw_baud


# ---------------------------------------------------------------------------
# Resampling — one sample per bit, taken at mid-cell
# ---------------------------------------------------------------------------

def resample_bits(times: list[float], bits: list[int], baud: float) -> list[int]:
    """
    Produce a clean bit list by sampling once per bit period at cell centre.
    """
    bit_period = 1.0 / baud
    t_end = times[-1]

    resampled: list[int] = []
    t = times[0] + bit_period / 2.0
    idx = 0

    while t <= t_end:
        while idx + 1 < len(times) and times[idx + 1] <= t:
            idx += 1
        resampled.append(bits[idx])
        t += bit_period

    return resampled


# ---------------------------------------------------------------------------
# Framing & decoding
# ---------------------------------------------------------------------------

def frame_bits(bit_stream: list[int], bits_per_frame: int, lsb_first: bool) -> list[int]:
    """Group bits into N-bit frames and return integer values."""
    values: list[int] = []
    for i in range(0, len(bit_stream) - bits_per_frame + 1, bits_per_frame):
        frame = bit_stream[i : i + bits_per_frame]
        if lsb_first:
            frame = frame[::-1]
        values.append(int("".join(str(b) for b in frame), 2))
    return values


def decode_values(values: list[int], encoding: str, bits_per_frame: int) -> list[str]:
    """Render integer frame values as the requested encoding."""
    result: list[str] = []
    for v in values:
        if encoding == "ascii":
            result.append(chr(v) if 32 <= v <= 126 else f"[{v:02X}]")
        elif encoding == "hex":
            result.append(f"{v:02X}")
        elif encoding == "decimal":
            result.append(str(v))
        else:  # binary
            result.append(f"{v:0{bits_per_frame}b}")
    return result


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_report(
    meta: dict,
    times: list[float],
    voltages: list[float],
    threshold: float,
    baud: float,
    bit_stream: list[int],
    frames: list[int],
    decoded: list[str],
    encoding: str,
    bits_per_frame: int,
    lsb_first: bool,
    inverted: bool,
) -> None:
    SEP = "=" * 60

    print(f"\n{SEP}")
    print("   OSCILLOSCOPE PAYLOAD DECODER")
    print(SEP)

    # Oscilloscope metadata
    if meta:
        print("\n[Oscilloscope metadata]")
        labels = {
            "record_length":   "Record length",
            "sample_rate":     "Sample rate (Hz)",
            "vertical_scale":  "Vertical scale",
            "vertical_offset": "Vertical offset",
            "horizontal_scale":"Horizontal scale",
        }
        for key, label in labels.items():
            if key in meta:
                print(f"  {label:<22}: {meta[key]}")

    # Signal summary
    v_min, v_max = min(voltages), max(voltages)
    duration = times[-1] - times[0]
    print(f"\n[Signal]")
    print(f"  Samples          : {len(voltages):,}")
    print(f"  Duration         : {duration:.6f} s  ({duration * 1e3:.3f} ms)")
    print(f"  Voltage range    : {v_min:.3f} V – {v_max:.3f} V")
    print(f"  Threshold        : {threshold:.3f} V")
    print(f"  Signal polarity  : {'inverted (active-low)' if inverted else 'normal (active-high)'}")

    # Bit stream info
    print(f"\n[Bit extraction]")
    print(f"  Detected baud    : {baud:,.1f} bps")
    print(f"  Bit period       : {1/baud*1e6:.3f} µs")
    print(f"  Bits extracted   : {len(bit_stream)}")
    print(f"  Bits per frame   : {bits_per_frame}")
    print(f"  Bit order        : {'LSB first' if lsb_first else 'MSB first'}")
    print(f"  Frames decoded   : {len(frames)}")

    # Raw bit stream
    stream_str = "".join(str(b) for b in bit_stream)
    print(f"\n[Raw bit stream]")
    for i in range(0, len(stream_str), 64):
        chunk = stream_str[i : i + 64]
        # Group into nibbles of 8 for readability
        spaced = " ".join(chunk[j : j + 8] for j in range(0, len(chunk), 8))
        print(f"  {spaced}")

    # Decoded payload
    print(f"\n[Decoded payload — {encoding.upper()}]")
    if encoding == "ascii":
        for i in range(0, len(decoded), 32):
            print(f"  {''.join(decoded[i : i + 32])}")
    else:
        for i in range(0, len(decoded), 16):
            print(f"  {' '.join(decoded[i : i + 16])}")

    # Hex dump (always shown as a reference view)
    print(f"\n[Hex dump + ASCII]")
    for i in range(0, len(frames), 16):
        row = frames[i : i + 16]
        addr = f"{i:04X}"
        hex_part = " ".join(f"{v:02X}" for v in row)
        ascii_part = "".join(chr(v) if 32 <= v <= 126 else "." for v in row)
        print(f"  {addr}  {hex_part:<48}  {ascii_part}")

    print(f"\n{SEP}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Decode a binary payload from an oscilloscope CSV capture.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("csv_file", help="Path to the oscilloscope CSV file")
    p.add_argument(
        "--threshold", type=float, default=None,
        help="Voltage threshold for logic HIGH (default: auto midpoint)",
    )
    p.add_argument(
        "--baud", type=float, default=None,
        help="Baud rate in bps (default: auto-detected from transitions)",
    )
    p.add_argument(
        "--bits", type=int, default=8, choices=[5, 6, 7, 8],
        help="Bits per frame (default: 8)",
    )
    p.add_argument(
        "--lsb-first", action="store_true",
        help="First received bit is LSB — typical for UART (default: MSB first)",
    )
    p.add_argument(
        "--invert", action="store_true",
        help="Invert logic levels — use for active-low / idle-high signals",
    )
    p.add_argument(
        "--encoding", default="ascii",
        choices=["ascii", "hex", "decimal", "binary"],
        help="Output encoding for decoded frames (default: ascii)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    path = Path(args.csv_file)
    if not path.exists():
        sys.exit(f"Error: file not found — {path}")

    print(f"Loading {path} …")
    meta, times, voltages = load_csv(str(path))
    print(f"  {len(times):,} samples over {(times[-1]-times[0])*1e3:.3f} ms")

    threshold = args.threshold if args.threshold is not None else auto_threshold(voltages)
    raw_bits  = to_bits(voltages, threshold, args.invert)

    baud = args.baud if args.baud is not None else detect_baud(times, raw_bits)
    print(f"  Baud rate: {baud:,.1f} bps")

    bit_stream = resample_bits(times, raw_bits, baud)
    frames     = frame_bits(bit_stream, args.bits, args.lsb_first)
    decoded    = decode_values(frames, args.encoding, args.bits)

    print_report(
        meta, times, voltages, threshold, baud,
        bit_stream, frames, decoded,
        args.encoding, args.bits, args.lsb_first, args.invert,
    )


if __name__ == "__main__":
    main()
