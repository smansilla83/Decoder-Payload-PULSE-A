"""
Streamlit front-end for the Oscilloscope CSV Payload Decoder.

Run with:
  streamlit run app.py
"""

import numpy as np
import streamlit as st
import plotly.graph_objects as go

from theme import apply_theme, render_nav, plot_colors
from pdf_report import build_pdf
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
# Page config + theme
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Payload Decoder — PULSE-A",
    page_icon="📡",
    layout="wide",
)
LIGHT = apply_theme()
pc    = plot_colors(LIGHT)

# ---------------------------------------------------------------------------
# Title + nav
# ---------------------------------------------------------------------------

st.title("📡 Oscilloscope Payload Decoder")
st.caption("Upload a Tektronix (or compatible) CSV capture to extract and decode the bit stream.")
render_nav("decoder")

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
    bits_per_frame = st.selectbox("Bits per frame", options=[8, 7, 6, 5], index=0)
    lsb_first = st.checkbox("LSB first (UART)", value=False)
    invert    = st.checkbox("Invert signal (active-low)", value=False)

    st.divider()
    st.subheader("Threshold")
    auto_thresh      = st.checkbox("Auto threshold (midpoint)", value=True)
    manual_threshold = st.number_input("Manual threshold (V)", value=2.5, step=0.1,
                                       disabled=auto_thresh)

    st.subheader("Baud rate")
    auto_baud   = st.checkbox("Auto-detect baud rate", value=True)
    manual_baud = st.number_input("Manual baud rate (bps)", value=9600, step=100,
                                  disabled=auto_baud)

    st.divider()
    st.subheader("FFT")
    fft_top_n  = st.slider("Dominant frequencies to show", 3, 10, 5)
    fft_log    = st.checkbox("Log scale (Y axis)", value=False)

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
# Decode
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
        for k, label in labels.items():
            if k in meta:
                st.text(f"{label:<22}: {meta[k]}")

# ---------------------------------------------------------------------------
# Signal plot
# ---------------------------------------------------------------------------

st.subheader("Signal")

MAX_PTS = 10_000
step = max(1, len(times) // MAX_PTS)
t_ms = [t * 1e3 for t in times[::step]]
v_ds = voltages[::step]

fig = go.Figure()
fig.add_trace(go.Scatter(x=t_ms, y=v_ds, mode="lines", name="Voltage",
                         line=dict(color="#1f77b4", width=1)))
fig.add_hline(y=threshold, line=dict(color="red", dash="dash", width=1),
              annotation_text=f"Threshold {threshold:.2f} V",
              annotation_position="bottom right")
fig.update_layout(
    xaxis_title="Time (ms)", yaxis_title="Voltage (V)",
    margin=dict(l=0, r=0, t=10, b=0), height=320,
    legend=dict(orientation="h"),
    paper_bgcolor=pc["bg"], plot_bgcolor=pc["bg"], font=dict(color=pc["text"]),
    xaxis=dict(rangeslider=dict(visible=True, thickness=0.08), gridcolor=pc["grid"]),
    yaxis=dict(gridcolor=pc["grid"]),
)
st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

duration = times[-1] - times[0]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Samples",       f"{len(voltages):,}")
c2.metric("Duration",      f"{duration*1e3:.3f} ms")
c3.metric("Voltage range", f"{min(voltages):.2f} – {max(voltages):.2f} V")
c4.metric("Threshold",     f"{threshold:.3f} V")

c5, c6, c7, c8 = st.columns(4)
c5.metric("Baud rate",     f"{baud:,.0f} bps")
c6.metric("Bit period",    f"{1/baud*1e6:.2f} µs")
c7.metric("Bits extracted",f"{len(bit_stream)}")
c8.metric("Frames",        f"{len(frames)}")

# ---------------------------------------------------------------------------
# Fourier Transform (FFT)
# ---------------------------------------------------------------------------

st.subheader("Frequency Spectrum (FFT)")

v_arr = np.array(voltages)
N     = len(v_arr)
sample_rate_hz = N / duration

# Remove DC offset before FFT
fft_vals  = np.fft.rfft(v_arr - np.mean(v_arr))
fft_freqs = np.fft.rfftfreq(N, d=1.0 / sample_rate_hz)
fft_mag   = np.abs(fft_vals) / (N / 2)

# Choose display unit
max_freq = fft_freqs[-1]
if max_freq >= 1e6:
    fscale, funit = 1e-6, "MHz"
elif max_freq >= 1e3:
    fscale, funit = 1e-3, "kHz"
else:
    fscale, funit = 1.0, "Hz"

# Top N dominant (skip DC bucket)
nz_mask   = fft_freqs > 0
top_idx   = np.argsort(fft_mag[nz_mask])[::-1][:fft_top_n]
dom_freqs = fft_freqs[nz_mask][top_idx]
dom_mags  = fft_mag[nz_mask][top_idx]

fig_fft = go.Figure()
fig_fft.add_trace(go.Scatter(
    x=fft_freqs[nz_mask] * fscale,
    y=fft_mag[nz_mask],
    mode="lines", name="Magnitude",
    line=dict(color="#e8a000", width=1),
))
fig_fft.add_trace(go.Scatter(
    x=dom_freqs * fscale, y=dom_mags,
    mode="markers", name="Dominant",
    marker=dict(color="#e83030", size=7, symbol="circle"),
))
fig_fft.update_layout(
    xaxis_title=f"Frequency ({funit})",
    yaxis_title="Magnitude (V)" + (" [log]" if fft_log else ""),
    yaxis_type="log" if fft_log else "linear",
    margin=dict(l=0, r=0, t=10, b=0), height=280,
    legend=dict(orientation="h"),
    paper_bgcolor=pc["bg"], plot_bgcolor=pc["bg"], font=dict(color=pc["text"]),
    xaxis=dict(gridcolor=pc["grid"]),
    yaxis=dict(gridcolor=pc["grid"]),
)
st.plotly_chart(fig_fft, use_container_width=True)

# Dominant frequency table
fund_freq = dom_freqs[0] if len(dom_freqs) > 0 else None

col_freq, col_table = st.columns([1, 2])
with col_freq:
    if fund_freq:
        st.metric("Fundamental frequency", f"{fund_freq*fscale:.4f} {funit}")
        st.metric("Nyquist limit",         f"{max_freq*fscale:.4f} {funit}")

with col_table:
    rows = {
        f"Frequency ({funit})": [f"{f*fscale:.4f}" for f in dom_freqs],
        "Magnitude (V)":        [f"{m:.5f}"        for m in dom_mags],
        "Period (µs)":          [f"{1/f*1e6:.2f}"  for f in dom_freqs],
    }
    import pandas as pd
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Results tabs
# ---------------------------------------------------------------------------

st.subheader("Results")
tab_bits, tab_decoded, tab_hex = st.tabs(["Raw bit stream", "Decoded payload", "Hex dump"])

with tab_bits:
    stream_str = "".join(str(b) for b in bit_stream)
    lines_out  = []
    for i in range(0, len(stream_str), 64):
        chunk = stream_str[i : i + 64]
        lines_out.append(" ".join(chunk[j : j + 8] for j in range(0, len(chunk), 8)))
    st.code("\n".join(lines_out), language=None)

with tab_decoded:
    if encoding == "ascii":
        st.code("".join(decoded), language=None)
    else:
        st.code("\n".join(" ".join(decoded[i:i+16]) for i in range(0, len(decoded), 16)),
                language=None)
    st.download_button("Download raw bytes", data=bytes(frames),
                       file_name="decoded_payload.bin", mime="application/octet-stream")

with tab_hex:
    hex_lines = []
    for i in range(0, len(frames), 16):
        row      = frames[i : i + 16]
        hex_part = " ".join(f"{v:02X}" for v in row)
        asc_part = "".join(chr(v) if 32 <= v <= 126 else "." for v in row)
        hex_lines.append(f"{i:04X}  {hex_part:<48}  {asc_part}")
    st.code("\n".join(hex_lines), language=None)

# ---------------------------------------------------------------------------
# Export — PDF report
# ---------------------------------------------------------------------------

st.divider()
st.markdown("**Export**")

pdf_bytes = build_pdf(
    filename=uploaded.name, meta=meta, times=times, voltages=voltages,
    threshold=threshold, baud=baud, bit_stream=bit_stream, frames=frames,
    decoded=decoded, encoding=encoding, bits_per_frame=bits_per_frame,
    lsb_first=lsb_first, inverted=invert,
)
st.download_button(
    label="📄 Download PDF Report",
    data=pdf_bytes,
    file_name=uploaded.name.rsplit(".", 1)[0] + "_report.pdf",
    mime="application/pdf",
)
