"""
Streamlit front-end for the Oscilloscope CSV Payload Decoder.

Run with:
  streamlit run app.py
"""

import streamlit as st
import plotly.graph_objects as go

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
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Payload Decoder — PULSE-A",
    page_icon="📡",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Theme toggle (session state)
# ---------------------------------------------------------------------------

if "light_mode" not in st.session_state:
    st.session_state.light_mode = False

LIGHT = st.session_state.light_mode

THEME_CSS = """
<style>
  /* ── Page & sidebar backgrounds ── */
  html, body, .stApp, .main, .block-container {
    background-color: #f0f2f6 !important;
  }
  [data-testid="stSidebar"],
  [data-testid="stSidebar"] > div:first-child {
    background-color: #e2e6ef !important;
  }

  /* ── All text dark ── */
  .stApp, .stApp p, .stApp span, .stApp div,
  .stApp label, .stApp h1, .stApp h2, .stApp h3,
  .stApp h4, .stApp h5, .stApp h6, .stApp li,
  .stApp td, .stApp th, .stApp caption,
  [data-testid="stSidebar"] * {
    color: #1a1a2e !important;
  }

  /* ── File uploader ── */
  [data-testid="stFileUploadDropzone"],
  [data-testid="stFileUploadDropzone"] > div {
    background-color: #dde3ee !important;
    border-color: #9aa5be !important;
  }
  [data-testid="stFileUploadDropzone"] *,
  [data-testid="stFileUploadDropzone"] small {
    color: #3a3a5a !important;
  }
  [data-testid="stFileUploadDropzone"] button {
    background-color: #c8d0e0 !important;
    color: #1a1a2e !important;
    border-color: #9aa5be !important;
  }

  /* ── Selectbox / dropdowns / inputs ── */
  [data-baseweb="select"] > div,
  [data-baseweb="select"] div[class*="ValueContainer"],
  [data-baseweb="input"] > div,
  [data-baseweb="base-input"] {
    background-color: #dde3ee !important;
    border-color: #9aa5be !important;
  }
  [data-baseweb="select"] *,
  [data-baseweb="input"] * {
    background-color: #dde3ee !important;
    color: #1a1a2e !important;
  }
  [data-baseweb="popover"] div,
  [data-baseweb="menu"] {
    background-color: #dde3ee !important;
    color: #1a1a2e !important;
  }
  [data-baseweb="option"]:hover {
    background-color: #c8d0e0 !important;
  }

  /* ── Number inputs ── */
  input[type="number"], input[type="text"] {
    background-color: #dde3ee !important;
    color: #1a1a2e !important;
    border-color: #9aa5be !important;
  }

  /* ── Checkboxes labels ── */
  [data-testid="stCheckbox"] span { color: #1a1a2e !important; }

  /* ── Buttons ── */
  [data-testid="stBaseButton-secondary"],
  button[kind="secondary"] {
    background-color: #c8d0e0 !important;
    color: #1a1a2e !important;
    border-color: #9aa5be !important;
  }

  /* ── Alert / info boxes ── */
  [data-testid="stAlert"],
  [data-testid="stAlertContainer"] {
    background-color: #d6e4f7 !important;
    color: #1a1a2e !important;
  }
  [data-testid="stAlert"] * { color: #1a1a2e !important; }

  /* ── Metrics ── */
  [data-testid="stMetricValue"] { color: #1a1a2e !important; }
  [data-testid="stMetricLabel"] { color: #4a4a6a !important; }
  [data-testid="stMetricDelta"] { color: #2a6a2a !important; }

  /* ── Tabs ── */
  [data-baseweb="tab-list"]     { background-color: #d8dfe8 !important; }
  [data-baseweb="tab"]          { background-color: transparent !important;
                                   color: #1a1a2e !important; }
  [aria-selected="true"]        { background-color: #c0cad8 !important; }
  [data-baseweb="tab-panel"]    { background-color: #f0f2f6 !important; }

  /* ── Code / preformatted ── */
  pre, code,
  [data-testid="stCode"] pre,
  .stCodeBlock, .stCodeBlock * {
    background-color: #e0e5ef !important;
    color: #1a1a2e !important;
  }

  /* ── Expanders ── */
  [data-testid="stExpander"],
  [data-testid="stExpander"] > details {
    background-color: #e8ecf5 !important;
    border-color: #b0b8cc !important;
  }
  [data-testid="stExpander"] summary { color: #1a1a2e !important; }

  /* ── Dividers ── */
  hr { border-color: #b8c2d4 !important; }

  /* ── Caption / small text ── */
  .stCaption, [data-testid="stCaptionContainer"] * {
    color: #4a4a6a !important;
  }

  /* ── Page link buttons ── */
  [data-testid="stPageLink"] a,
  [data-testid="stPageLink"] a * {
    color: #1a1a2e !important;
  }
  [data-testid="stPageLink-active"] a {
    background-color: #c0cad8 !important;
  }
</style>
""" if LIGHT else ""

PRINT_CSS = """
<style>
@media print {
    [data-testid="stSidebar"],
    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    [data-testid="stFileUploader"],
    section[data-testid="stFileUploadDropzone"],
    .stDownloadButton,
    .stButton,
    footer { display: none !important; }
    .block-container { padding: 1rem !important; }
}
</style>
"""

st.markdown(PRINT_CSS + THEME_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Title + nav bar
# ---------------------------------------------------------------------------

st.title("📡 Oscilloscope Payload Decoder")
st.caption("Upload a Tektronix (or compatible) CSV capture to extract and decode the bit stream.")

nav1, nav2, nav3, _, theme_col = st.columns([1, 1, 1, 4, 1])
with nav1:
    st.page_link("app.py", label="🏠 Decoder")
with nav2:
    st.page_link("pages/Compare.py", label="🔀 Compare")
with nav3:
    st.page_link("pages/Reference.py", label="📖 Reference")
with theme_col:
    label = "☀️ Light" if not LIGHT else "🌙 Dark"
    if st.button(label, key="theme_toggle"):
        st.session_state.light_mode = not st.session_state.light_mode
        st.rerun()

st.divider()

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
# Signal plot — with range slider for long captures
# ---------------------------------------------------------------------------

st.subheader("Signal")

MAX_PLOT_POINTS = 10_000
step = max(1, len(times) // MAX_PLOT_POINTS)
t_ms = [t * 1e3 for t in times[::step]]
v_ds = voltages[::step]

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=t_ms, y=v_ds,
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

plot_bg   = "#ffffff" if LIGHT else "#0e1117"
plot_text = "#1a1a2e" if LIGHT else "#fafafa"
fig.update_layout(
    xaxis_title="Time (ms)",
    yaxis_title="Voltage (V)",
    margin=dict(l=0, r=0, t=10, b=0),
    height=340,
    legend=dict(orientation="h"),
    paper_bgcolor=plot_bg,
    plot_bgcolor=plot_bg,
    font=dict(color=plot_text),
    xaxis=dict(
        rangeslider=dict(visible=True, thickness=0.08),
        gridcolor="#cccccc" if LIGHT else "#333333",
    ),
    yaxis=dict(gridcolor="#cccccc" if LIGHT else "#333333"),
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
    lines_out = []
    for i in range(0, len(stream_str), 64):
        chunk = stream_str[i : i + 64]
        lines_out.append(" ".join(chunk[j : j + 8] for j in range(0, len(chunk), 8)))
    st.code("\n".join(lines_out), language=None)

with tab_decoded:
    if encoding == "ascii":
        st.code("".join(decoded), language=None)
    else:
        rows = []
        for i in range(0, len(decoded), 16):
            rows.append(" ".join(decoded[i : i + 16]))
        st.code("\n".join(rows), language=None)

    st.download_button(
        "Download raw bytes",
        data=bytes(frames),
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

# ---------------------------------------------------------------------------
# Export — formatted PDF report
# ---------------------------------------------------------------------------

st.divider()
st.markdown("**Export**")

pdf_bytes = build_pdf(
    filename    = uploaded.name,
    meta        = meta,
    times       = times,
    voltages    = voltages,
    threshold   = threshold,
    baud        = baud,
    bit_stream  = bit_stream,
    frames      = frames,
    decoded     = decoded,
    encoding    = encoding,
    bits_per_frame = bits_per_frame,
    lsb_first   = lsb_first,
    inverted    = invert,
)

st.download_button(
    label     = "📄 Download PDF Report",
    data      = pdf_bytes,
    file_name = uploaded.name.rsplit(".", 1)[0] + "_report.pdf",
    mime      = "application/pdf",
)
