"""
Reference page — glossary of all terms used in the decoder.
"""

import streamlit as st

from theme import apply_theme, render_nav

st.set_page_config(
    page_title="Reference — PULSE-A",
    page_icon="📖",
    layout="wide",
)
apply_theme()

st.title("📖 Reference Guide")
st.caption("Explanations of every term and setting used in the payload decoder.")
render_nav("reference")

# ---------------------------------------------------------------------------
st.header("Signal basics")

with st.expander("Sample rate", expanded=True):
    st.markdown("""
The **sample rate** is how many voltage measurements the oscilloscope takes per second, expressed in Hz (samples/s).

- A 100 MHz sample rate means 100,000,000 readings per second.
- Higher sample rates capture faster signals more accurately.
- The sample rate must be at least **twice** the highest frequency in the signal (Nyquist theorem) to reconstruct it correctly.

> *Example:* To decode a 9600 baud signal, you need at least ~19,200 Hz sample rate. 100 MHz gives you far more than enough.
""")

with st.expander("Voltage range"):
    st.markdown("""
The **voltage range** is the span between the lowest and highest voltage measured in the capture.

- For 3.3 V logic: typically 0 V (low) to 3.3 V (high).
- For 5 V logic: typically 0 V to 5 V.
- The decoder uses this range to automatically calculate the threshold if you leave auto-threshold enabled.
""")

with st.expander("Duration"):
    st.markdown("""
The **duration** is the total time span of the captured signal, from the first sample to the last.

- Displayed in milliseconds (ms).
- A longer capture contains more bits and therefore more data.
- Duration = (number of samples) ÷ (sample rate).
""")

# ---------------------------------------------------------------------------
st.header("Threshold")

with st.expander("What is the threshold?", expanded=True):
    st.markdown("""
The **threshold** is the voltage value used to decide whether each sample is a logic **1** (HIGH) or logic **0** (LOW).

- Any sample **at or above** the threshold → bit = 1
- Any sample **below** the threshold → bit = 0

**Auto threshold** sets it to the midpoint between the signal's minimum and maximum voltage:

```
threshold = (V_max + V_min) / 2
```

> *Example:* For a 0–5 V signal, auto threshold = 2.5 V.

Use **manual threshold** if your signal has noise, a non-standard voltage swing, or an asymmetric waveform.
""")

with st.expander("Inverted signal (active-low)"):
    st.markdown("""
Some protocols transmit data with **inverted polarity** — the line sits HIGH when idle and pulses LOW for data. This is called **active-low** or **idle-high**.

- **UART (RS-232)** is a common example: idle = HIGH, start bit = LOW.
- Enabling **Invert signal** flips every 0 → 1 and 1 → 0 after thresholding.

If your decoded output looks like garbage but the signal looks clean, try toggling this option.
""")

# ---------------------------------------------------------------------------
st.header("Baud rate & bit period")

with st.expander("Baud rate", expanded=True):
    st.markdown("""
The **baud rate** is the number of **symbols transmitted per second**, measured in baud (Bd) or bits per second (bps) for binary signals.

Common baud rates for serial protocols:

| Baud rate | Typical use |
|-----------|-------------|
| 9600      | Basic UART, sensors |
| 115200    | Fast UART, microcontrollers |
| 1,000,000 | High-speed serial |

**Auto-detect** finds the shortest run of identical bits in the signal; that duration equals one bit period, giving the baud rate.

If auto-detect gives a wrong result (e.g., the signal starts with a long idle), enter the baud rate manually.
""")

with st.expander("Bit period"):
    st.markdown("""
The **bit period** is the duration of one single bit, i.e. how long the line stays at a given level to represent one 1 or 0.

```
bit period = 1 / baud rate
```

| Baud rate | Bit period |
|-----------|------------|
| 9,600     | 104.2 µs   |
| 115,200   | 8.68 µs    |
| 1,000,000 | 1.00 µs    |

The decoder re-samples the signal once per bit period (at the centre of each bit cell) to extract a clean bit stream regardless of the original sample rate.
""")

# ---------------------------------------------------------------------------
st.header("Framing")

with st.expander("Bits per frame", expanded=True):
    st.markdown("""
A **frame** is a fixed-size group of bits that represents one unit of data (e.g., one character or one byte).

| Bits per frame | Common use |
|----------------|------------|
| 8              | Standard byte, ASCII (7-bit + parity), most protocols |
| 7              | 7-bit ASCII (no parity bit) |
| 6              | Rare, some legacy teleprinter codes |
| 5              | Baudot / Murray code (old telex) |

The decoder groups the extracted bit stream into frames of the chosen size and converts each frame to an integer value.
""")

with st.expander("Bit order — LSB first vs MSB first"):
    st.markdown("""
**Bit order** controls which bit in the frame represents the most significant value.

- **MSB first** (default): the *first* received bit is the most significant bit (2⁷ for an 8-bit frame). Used in SPI, I²C, and most network protocols.
- **LSB first**: the *first* received bit is the least significant bit (2⁰). Used in **UART** and many microcontroller peripherals.

> *Example:* Receiving bits `1 0 1 1 0 0 0 0`:
>
> - MSB first → 0b10110000 = 0xB0 = 176
> - LSB first → 0b00001101 = 0x0D = 13 (carriage return)

If decoded text looks like mirrored or nonsense characters, try switching bit order.
""")

# ---------------------------------------------------------------------------
st.header("Output encodings")

with st.expander("ASCII", expanded=True):
    st.markdown("""
**ASCII** (American Standard Code for Information Interchange) maps each 7-bit or 8-bit value to a printable character.

- Values 32–126 map to readable characters (letters, digits, punctuation).
- Values outside that range are shown as `[XX]` (hex) to avoid display issues.
- Use this when decoding text-based serial protocols (UART terminal output, AT commands, NMEA GPS sentences, etc.).
""")

with st.expander("Hex (hexadecimal)"):
    st.markdown("""
**Hexadecimal** represents each byte as two characters from 0–9 and A–F.

- Each hex digit represents 4 bits (a nibble).
- One byte (8 bits) = two hex digits, e.g. `FF`, `1A`, `00`.
- Easier to read than raw binary for longer payloads.
- Useful when the data is not human-readable text (sensor readings, binary protocols, checksums).

> *Example:* 0b10110000 = 0xB0 = 176 decimal
""")

with st.expander("Binary"):
    st.markdown("""
**Binary** displays each frame as a string of 1s and 0s.

- Each digit is one bit.
- An 8-bit frame is shown as 8 digits, e.g. `10110000`.
- Useful for inspecting individual bit values and verifying framing alignment.
""")

with st.expander("Decimal"):
    st.markdown("""
**Decimal** shows the numeric value of each frame in base 10.

- An 8-bit frame can range from 0 to 255.
- Useful when the payload contains numeric sensor data or counts.
""")

# ---------------------------------------------------------------------------
st.header("Result panels")

with st.expander("Raw bit stream"):
    st.markdown("""
The **raw bit stream** is the sequence of 1s and 0s extracted from the signal *before* framing.

- Bits are shown in the order they were received.
- Grouped in blocks of 8, with 64 bits per line.
- Useful for verifying that the baud rate and threshold are correctly set — the transitions should look clean and regular.
""")

with st.expander("Hex dump"):
    st.markdown("""
The **hex dump** is a standard format for inspecting raw binary data.

Each row contains three columns:

```
ADDR  hex bytes (up to 16 per row)  ASCII representation
0000  48 65 6C 6C 6F 20 57 6F 72 6C 64 0D 0A ...  Hello World..
```

- **ADDR** — byte offset from the start of the decoded payload (in hex).
- **Hex bytes** — each byte shown as two hex digits.
- **ASCII** — printable characters shown as-is; non-printable shown as `.`.

This view is useful for finding protocol headers, checksums, or non-printable control bytes alongside the human-readable content.
""")

# ---------------------------------------------------------------------------
st.header("Fourier Analysis (FFT)")

with st.expander("What is the Fourier Transform?", expanded=True):
    st.markdown("""
The **Fourier Transform** decomposes a signal from the **time domain** into the **frequency domain**.

- **Time domain** — voltage measured over time (what the oscilloscope shows).
- **Frequency domain** — how much of each frequency is present in the signal.

The decoder uses the **Fast Fourier Transform (FFT)**, which is a computationally efficient algorithm for computing the Discrete Fourier Transform (DFT) on a sampled signal.

**Why is this useful?**
- Identify the fundamental frequency of a serial signal
- Detect noise, interference, or unexpected harmonics
- Verify that the baud rate matches the dominant frequency
- Diagnose signal integrity issues (ringing, aliasing, EMI)

> *Example:* A 9,600 baud UART signal will show a dominant frequency near 9,600 Hz and harmonics at 28,800 Hz, 48,000 Hz, etc.
""")

with st.expander("Frequency spectrum — reading the chart"):
    st.markdown("""
The **frequency spectrum** chart shows:

- **X axis** — frequency in Hz, kHz, or MHz (auto-scaled to the signal)
- **Y axis** — magnitude in volts — how strongly that frequency is present
- **Orange line** — the full spectrum
- **Red dots** — the top N dominant (strongest) frequencies

The chart excludes the **DC component** (0 Hz) which is simply the average voltage of the signal — not useful for identifying data frequencies.
""")

with st.expander("Fundamental frequency"):
    st.markdown("""
The **fundamental frequency** is the lowest and usually strongest frequency in the spectrum. For a periodic signal it equals **1 / period**.

For a serial data signal the fundamental is directly related to the baud rate:
- A square wave at 9,600 baud has a fundamental near **9,600 Hz**
- The exact value depends on the data pattern — a long run of alternating 1/0 bits creates the clearest fundamental

> Compare the fundamental against the detected baud rate to cross-check the decoding.
""")

with st.expander("Harmonics"):
    st.markdown("""
**Harmonics** are frequency components at integer multiples of the fundamental.

A **square wave** is made up of odd harmonics only:

```
f, 3f, 5f, 7f, 9f, ...
```

Where f is the fundamental. Their magnitudes decrease as 1/n (the 3rd harmonic has ⅓ the magnitude of the fundamental).

| Harmonic | Multiplier | Relative magnitude |
|----------|------------|-------------------|
| 1st (fundamental) | 1× | 1.000 |
| 3rd              | 3× | 0.333 |
| 5th              | 5× | 0.200 |
| 7th              | 7× | 0.143 |

If you see even harmonics (2f, 4f) it can indicate signal asymmetry, noise, or a non-square waveform.
""")

with st.expander("Nyquist frequency"):
    st.markdown("""
The **Nyquist frequency** is the highest frequency the oscilloscope can correctly measure:

```
f_nyquist = sample_rate / 2
```

| Sample rate | Nyquist limit |
|-------------|--------------|
| 100 MHz     | 50 MHz       |
| 1 GSa/s     | 500 MHz      |

Any frequency above the Nyquist limit will appear **aliased** — folded back into the spectrum as a false lower frequency. Always ensure your sample rate is at least twice the highest frequency of interest.
""")

with st.expander("Log scale (Y axis)"):
    st.markdown("""
The **log scale** option switches the magnitude axis to a logarithmic scale (dB-like view).

- Useful when dominant peaks are much larger than the harmonics — in linear scale the harmonics become invisible
- Makes it easier to see weak frequency components and noise floor
- Harmonic relationships become evenly spaced on the log scale

Toggle this in the **FFT** section of the sidebar.
""")
