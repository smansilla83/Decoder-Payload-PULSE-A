"""
Signal comparison page — overlay two oscilloscope CSV captures.
"""

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

st.set_page_config(
    page_title="Compare — PULSE-A",
    page_icon="🔀",
    layout="wide",
)

st.title("🔀 Signal Comparison")
st.caption("Upload two CSV captures to overlay and compare their signals and decoded payloads.")

# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

col_a, col_b = st.columns(2)
with col_a:
    st.markdown("**Signal A**")
    file_a = st.file_uploader("Signal A", type=["csv", "txt"], key="file_a",
                               label_visibility="collapsed")
with col_b:
    st.markdown("**Signal B**")
    file_b = st.file_uploader("Signal B", type=["csv", "txt"], key="file_b",
                               label_visibility="collapsed")

if file_a is None and file_b is None:
    st.info("Upload at least one CSV to begin.")
    st.stop()

# ---------------------------------------------------------------------------
# Settings (shared, in sidebar)
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Decode settings")
    encoding       = st.selectbox("Output encoding", ["ascii", "hex", "decimal", "binary"])
    bits_per_frame = st.selectbox("Bits per frame", [8, 7, 6, 5])
    lsb_first      = st.checkbox("LSB first (UART)", value=False)
    invert         = st.checkbox("Invert signals (active-low)", value=False)

    st.divider()
    st.subheader("Threshold")
    auto_thresh      = st.checkbox("Auto threshold", value=True)
    manual_threshold = st.number_input("Manual threshold (V)", value=2.5, step=0.1,
                                       disabled=auto_thresh)
    st.subheader("Baud rate")
    auto_baud   = st.checkbox("Auto-detect baud rate", value=True)
    manual_baud = st.number_input("Manual baud rate (bps)", value=9600, step=100,
                                  disabled=auto_baud)

# ---------------------------------------------------------------------------
# Helper: parse one uploaded file → all decoded artefacts
# ---------------------------------------------------------------------------

def process(uploaded) -> dict | None:
    if uploaded is None:
        return None
    try:
        text = uploaded.read().decode("utf-8-sig")
        meta, times, voltages = parse_csv_content(text)
    except Exception as e:
        st.error(f"Failed to parse {uploaded.name}: {e}")
        return None

    threshold = auto_threshold(voltages) if auto_thresh else float(manual_threshold)
    raw_bits  = to_bits(voltages, threshold, invert)

    try:
        baud = detect_baud(times, raw_bits) if auto_baud else float(manual_baud)
    except ValueError:
        baud = float(manual_baud)

    bit_stream = resample_bits(times, raw_bits, baud)
    frames     = frame_bits(bit_stream, bits_per_frame, lsb_first)
    decoded    = decode_values(frames, encoding, bits_per_frame)

    return dict(
        name=uploaded.name, meta=meta, times=times, voltages=voltages,
        threshold=threshold, baud=baud, bit_stream=bit_stream,
        frames=frames, decoded=decoded,
    )

sig_a = process(file_a)
sig_b = process(file_b)

# ---------------------------------------------------------------------------
# Overlaid signal plot
# ---------------------------------------------------------------------------

st.subheader("Signal overlay")

MAX_PTS = 10_000
COLORS  = {"A": "#1f77b4", "B": "#ff7f0e"}

fig = go.Figure()

for label, sig in [("A", sig_a), ("B", sig_b)]:
    if sig is None:
        continue
    times, voltages = sig["times"], sig["voltages"]
    step  = max(1, len(times) // MAX_PTS)
    t_ms  = [t * 1e3 for t in times[::step]]
    v_ds  = voltages[::step]
    fig.add_trace(go.Scatter(
        x=t_ms, y=v_ds,
        mode="lines",
        name=f"Signal {label} — {sig['name']}",
        line=dict(color=COLORS[label], width=1),
    ))
    fig.add_hline(
        y=sig["threshold"],
        line=dict(color=COLORS[label], dash="dot", width=1),
        annotation_text=f"Thresh {label} {sig['threshold']:.2f} V",
        annotation_position="top right" if label == "A" else "bottom right",
    )

fig.update_layout(
    xaxis_title="Time (ms)",
    yaxis_title="Voltage (V)",
    margin=dict(l=0, r=0, t=10, b=0),
    height=360,
    legend=dict(orientation="h"),
    xaxis=dict(
        rangeslider=dict(visible=True, thickness=0.08),
    ),
)
st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Side-by-side metrics
# ---------------------------------------------------------------------------

st.subheader("Signal metrics")
col_a, col_b = st.columns(2)

def show_metrics(col, sig, label):
    with col:
        if sig is None:
            st.info(f"No Signal {label} loaded.")
            return
        st.markdown(f"**Signal {label} — {sig['name']}**")
        times, voltages = sig["times"], sig["voltages"]
        duration = times[-1] - times[0]
        m1, m2 = st.columns(2)
        m1.metric("Samples",       f"{len(voltages):,}")
        m2.metric("Duration",      f"{duration*1e3:.3f} ms")
        m3, m4 = st.columns(2)
        m3.metric("Voltage range", f"{min(voltages):.2f} – {max(voltages):.2f} V")
        m4.metric("Threshold",     f"{sig['threshold']:.3f} V")
        m5, m6 = st.columns(2)
        m5.metric("Baud rate",     f"{sig['baud']:,.0f} bps")
        m6.metric("Bit period",    f"{1/sig['baud']*1e6:.2f} µs")
        m7, m8 = st.columns(2)
        m7.metric("Bits extracted",f"{len(sig['bit_stream'])}")
        m8.metric("Frames",        f"{len(sig['frames'])}")

show_metrics(col_a, sig_a, "A")
show_metrics(col_b, sig_b, "B")

# ---------------------------------------------------------------------------
# Side-by-side decoded output
# ---------------------------------------------------------------------------

st.subheader("Decoded payload comparison")
col_a, col_b = st.columns(2)

def show_decoded(col, sig, label):
    with col:
        if sig is None:
            st.info(f"No Signal {label} loaded.")
            return
        st.markdown(f"**Signal {label}**")
        tab_bits, tab_dec, tab_hex = st.tabs(["Bit stream", "Decoded", "Hex dump"])

        with tab_bits:
            stream_str = "".join(str(b) for b in sig["bit_stream"])
            lines_out = []
            for i in range(0, len(stream_str), 64):
                chunk = stream_str[i : i + 64]
                lines_out.append(" ".join(chunk[j : j + 8] for j in range(0, len(chunk), 8)))
            st.code("\n".join(lines_out), language=None)

        with tab_dec:
            decoded = sig["decoded"]
            if encoding == "ascii":
                st.code("".join(decoded), language=None)
            else:
                rows = [" ".join(decoded[i : i + 16]) for i in range(0, len(decoded), 16)]
                st.code("\n".join(rows), language=None)

        with tab_hex:
            frames = sig["frames"]
            hex_lines = []
            for i in range(0, len(frames), 16):
                row      = frames[i : i + 16]
                hex_part = " ".join(f"{v:02X}" for v in row)
                asc_part = "".join(chr(v) if 32 <= v <= 126 else "." for v in row)
                hex_lines.append(f"{i:04X}  {hex_part:<48}  {asc_part}")
            st.code("\n".join(hex_lines), language=None)

show_decoded(col_a, sig_a, "A")
show_decoded(col_b, sig_b, "B")

# ---------------------------------------------------------------------------
# Bit-stream diff
# ---------------------------------------------------------------------------

if sig_a and sig_b:
    st.subheader("Bit stream diff")
    bs_a = sig_a["bit_stream"]
    bs_b = sig_b["bit_stream"]
    min_len = min(len(bs_a), len(bs_b))
    diffs = [i for i in range(min_len) if bs_a[i] != bs_b[i]]

    if not diffs:
        st.success(f"Bit streams are identical over the first {min_len} bits.")
    else:
        st.warning(f"{len(diffs)} differing bit(s) in the first {min_len} compared.")
        diff_preview = ", ".join(str(i) for i in diffs[:40])
        if len(diffs) > 40:
            diff_preview += f" … (+{len(diffs)-40} more)"
        st.code(f"Differing bit positions: {diff_preview}", language=None)

    if len(bs_a) != len(bs_b):
        st.info(
            f"Signal A has {len(bs_a)} bits, Signal B has {len(bs_b)} bits "
            f"({'A longer' if len(bs_a) > len(bs_b) else 'B longer'} by "
            f"{abs(len(bs_a)-len(bs_b))} bits)."
        )
