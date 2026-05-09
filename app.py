"""
Streamlit front-end for the Oscilloscope CSV Payload Decoder.

Run with:
  streamlit run app.py
"""

import io
import streamlit as st
import plotly.graph_objects as go

from decoder_1 import (
    parse_csv_content,
    auto_threshold,
    to_bits,
    detect_baud,
    resample_bits,
    frame_bits,
    decode_values,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Payload Decoder — PULSE-A",
    page_icon="📡",
    layout="wide",
)

st.title("📡 Oscilloscope Payload Decoder")
st.caption("Upload a Tektronix (or compatible) CSV capture to extract and decode the bit stream.")

# ---------------------------------------------------------------------------
# Sidebar — settings
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Decode settings")

    encoding = st.selectbox(
        "Output encoding",
        options=["ascii", "hex", "decimal", "binary"],
        index=0,
    )

    bits_per_frame = st.selectbox(
        "Bits per frame",
        options=[8, 7, 6, 5],
        index=0,
    )

    lsb_first = st.checkbox("LSB first (UART)", value=False)
    invert    = st.checkbox("Invert signal (active-low)", value=False)

    st.divider()
    st.subheader("Threshold")
    auto_thresh = st.checkbox("Auto threshold (midpoint)", value=True)
    manual_threshold = st.number_input(
        "Manual threshold (V)", value=2.5, step=0.1,
        disabled=auto_thresh,
    )

    st.subheader("Baud rate")
    auto_baud = st.checkbox("Auto-detect baud rate", value=True)
    manual_baud = st.number_input(
        "Manual baud rate (bps)", value=9600, step=100,
        disabled=auto_baud,
    )

# ---------------------------------------------------------------------------
# File upload
# ---------------------------------------------------------------------------

uploaded = st.file_uploader(
    "Drop your oscilloscope CSV here",
    type=["csv", "txt"],
    label_visibility="collapsed",
)

if uploaded is None:
    st.info("Upload a CSV file to begin.")
    st.stop()

# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------

try:
    text = uploaded.read().decode("utf-8-sig")
    meta, times, voltages = parse_csv_content(text)
except Exception as e:
    st.error(f"Failed to parse CSV: {e}")
    st.stop()

# ---------------------------------------------------------------------------
# Threshold & bits
# ---------------------------------------------------------------------------

threshold = auto_threshold(voltages) if auto_thresh else float(manual_threshold)
raw_bits  = to_bits(voltages, threshold, invert)

try:
    baud = detect_baud(times, raw_bits) if auto_baud else float(manual_baud)
except ValueError as e:
    st.warning(str(e))
    baud = float(manual_baud)

bit_stream = resample_bits(times, raw_bits, baud)
frames     = frame_bits(bit_stream, bits_per_frame, lsb_first)
decoded    = decode_values(frames, encoding, bits_per_frame)

# ---------------------------------------------------------------------------
# Oscilloscope metadata
# ---------------------------------------------------------------------------

if meta:
    with st.expander("Oscilloscope metadata", expanded=False):
        labels = {
            "record_length":    "Record length",
            "sample_rate":      "Sample rate (Hz)",
            "vertical_scale":   "Vertical scale",
            "vertical_offset":  "Vertical offset",
            "horizontal_scale": "Horizontal scale",
        }
        for key, label in labels.items():
            if key in meta:
                st.text(f"{label:<22}: {meta[key]}")

# ---------------------------------------------------------------------------
# Signal plot
# ---------------------------------------------------------------------------

st.subheader("Signal")

# Downsample for display if the capture is very large (keep chart snappy)
MAX_PLOT_POINTS = 10_000
n = len(times)
step = max(1, n // MAX_PLOT_POINTS)
t_plot = times[::step]
v_plot = voltages[::step]
t_ms   = [t * 1e3 for t in t_plot]   # display in ms

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=t_ms, y=v_plot,
    mode="lines",
    name="Voltage",
    line=dict(color="#1f77b4", width=1),
))
fig.add_hline(
    y=threshold,
    line=dict(color="red", dash="dash", width=1),
    annotation_text=f"Threshold {threshold:.2f} V",
    annotation_position="bottom right",
)
fig.update_layout(
    xaxis_title="Time (ms)",
    yaxis_title="Voltage (V)",
    margin=dict(l=0, r=0, t=10, b=0),
    height=300,
    legend=dict(orientation="h"),
)
st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

duration = times[-1] - times[0]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Samples",       f"{len(voltages):,}")
col2.metric("Duration",      f"{duration*1e3:.3f} ms")
col3.metric("Voltage range", f"{min(voltages):.2f} – {max(voltages):.2f} V")
col4.metric("Threshold",     f"{threshold:.3f} V")

col5, col6, col7, col8 = st.columns(4)
col5.metric("Baud rate",     f"{baud:,.0f} bps")
col6.metric("Bit period",    f"{1/baud*1e6:.2f} µs")
col7.metric("Bits extracted",f"{len(bit_stream)}")
col8.metric("Frames",        f"{len(frames)}")

# ---------------------------------------------------------------------------
# Tabs — raw bits / decoded / hex dump
# ---------------------------------------------------------------------------

st.subheader("Results")
tab_bits, tab_decoded, tab_hex = st.tabs(["Raw bit stream", "Decoded payload", "Hex dump"])

with tab_bits:
    stream_str = "".join(str(b) for b in bit_stream)
    # Wrap into lines of 64, grouped in nibbles of 8
    lines_out = []
    for i in range(0, len(stream_str), 64):
        chunk = stream_str[i : i + 64]
        lines_out.append(" ".join(chunk[j : j + 8] for j in range(0, len(chunk), 8)))
    st.code("\n".join(lines_out), language=None)

with tab_decoded:
    if encoding == "ascii":
        payload = "".join(decoded)
        st.code(payload, language=None)
    else:
        # Format as rows of 16 tokens
        rows = []
        for i in range(0, len(decoded), 16):
            rows.append(" ".join(decoded[i : i + 16]))
        st.code("\n".join(rows), language=None)

    # Download button
    raw_bytes = bytes(frames)
    st.download_button(
        "Download raw bytes",
        data=raw_bytes,
        file_name="decoded_payload.bin",
        mime="application/octet-stream",
    )

with tab_hex:
    hex_lines = []
    for i in range(0, len(frames), 16):
        row      = frames[i : i + 16]
        addr     = f"{i:04X}"
        hex_part = " ".join(f"{v:02X}" for v in row)
        asc_part = "".join(chr(v) if 32 <= v <= 126 else "." for v in row)
        hex_lines.append(f"{addr}  {hex_part:<48}  {asc_part}")
    st.code("\n".join(hex_lines), language=None)
