"""
Signal comparison page — overlay two oscilloscope CSV captures.
"""

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from theme import apply_theme, render_nav, plot_colors
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
LIGHT = apply_theme()
pc    = plot_colors(LIGHT)

st.title("🔀 Signal Comparison")
st.caption("Upload two CSV captures to overlay and compare their signals and decoded payloads.")
render_nav("compare")

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
# Sidebar
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

    st.divider()
    st.subheader("Coupling analysis")
    coupling_mode = st.radio(
        "Expected relationship",
        ["Anti-phase (differential)", "In-phase (parallel)"],
        index=0,
    )
    align_method = st.radio(
        "Time alignment",
        ["Absolute time (same trigger)", "Align at first transition"],
        index=0,
    )

# ---------------------------------------------------------------------------
# Parse helper
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
        name=uploaded.name, meta=meta,
        times=np.array(times), voltages=np.array(voltages),
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
    step = max(1, len(sig["times"]) // MAX_PTS)
    t_ms = sig["times"][::step] * 1e3
    v_ds = sig["voltages"][::step]
    fig.add_trace(go.Scatter(x=t_ms, y=v_ds, mode="lines",
                             name=f"Signal {label} — {sig['name']}",
                             line=dict(color=COLORS[label], width=1)))
    fig.add_hline(y=sig["threshold"],
                  line=dict(color=COLORS[label], dash="dot", width=1),
                  annotation_text=f"Thresh {label} {sig['threshold']:.2f} V",
                  annotation_position="top right" if label == "A" else "bottom right")

fig.update_layout(
    xaxis_title="Time (ms)", yaxis_title="Voltage (V)",
    margin=dict(l=0, r=0, t=10, b=0), height=340,
    legend=dict(orientation="h"),
    paper_bgcolor=pc["bg"], plot_bgcolor=pc["bg"], font=dict(color=pc["text"]),
    xaxis=dict(rangeslider=dict(visible=True, thickness=0.08), gridcolor=pc["grid"]),
    yaxis=dict(gridcolor=pc["grid"]),
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
        duration = sig["times"][-1] - sig["times"][0]
        m1, m2 = st.columns(2)
        m1.metric("Samples",       f"{len(sig['voltages']):,}")
        m2.metric("Duration",      f"{duration*1e3:.3f} ms")
        m3, m4 = st.columns(2)
        m3.metric("Voltage range", f"{sig['voltages'].min():.2f} – {sig['voltages'].max():.2f} V")
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
# Decoded payload comparison
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
            s = "".join(str(b) for b in sig["bit_stream"])
            st.code("\n".join(
                " ".join(s[i:i+64][j:j+8] for j in range(0, len(s[i:i+64]), 8))
                for i in range(0, len(s), 64)
            ), language=None)
        with tab_dec:
            if encoding == "ascii":
                st.code("".join(sig["decoded"]), language=None)
            else:
                st.code("\n".join(
                    " ".join(sig["decoded"][i:i+16])
                    for i in range(0, len(sig["decoded"]), 16)
                ), language=None)
        with tab_hex:
            lines = []
            for i in range(0, len(sig["frames"]), 16):
                row = sig["frames"][i:i+16]
                lines.append(f"{i:04X}  {' '.join(f'{v:02X}' for v in row):<48}  "
                              f"{''.join(chr(v) if 32<=v<=126 else '.' for v in row)}")
            st.code("\n".join(lines), language=None)

show_decoded(col_a, sig_a, "A")
show_decoded(col_b, sig_b, "B")

# ---------------------------------------------------------------------------
# Bit-stream diff
# ---------------------------------------------------------------------------

if sig_a and sig_b:
    st.subheader("Bit stream diff")
    bs_a    = sig_a["bit_stream"]
    bs_b    = sig_b["bit_stream"]
    min_len = min(len(bs_a), len(bs_b))
    diffs   = [i for i in range(min_len) if bs_a[i] != bs_b[i]]

    if not diffs:
        st.success(f"Bit streams are identical over the first {min_len} bits.")
    else:
        st.warning(f"{len(diffs)} differing bit(s) in the first {min_len} compared.")
        preview = ", ".join(str(i) for i in diffs[:40])
        if len(diffs) > 40:
            preview += f" … (+{len(diffs)-40} more)"
        st.code(f"Differing positions: {preview}", language=None)

    if len(bs_a) != len(bs_b):
        longer = "A" if len(bs_a) > len(bs_b) else "B"
        st.info(f"Signal {longer} is longer by {abs(len(bs_a)-len(bs_b))} bits.")

# ---------------------------------------------------------------------------
# Coupling efficiency analysis (only when both signals are loaded)
# ---------------------------------------------------------------------------

if sig_a and sig_b:
    st.divider()
    st.subheader("⚡ Coupling Efficiency Analysis")
    st.caption(
        "Measures how well Signal B follows Signal A in the expected relationship "
        "(anti-phase for differential pairs, in-phase for parallel lines)."
    )

    anti_phase = coupling_mode.startswith("Anti")

    times_a    = sig_a["times"]
    voltages_a = sig_a["voltages"]
    times_b    = sig_b["times"]
    voltages_b = sig_b["voltages"]

    # ── 1. Find common time window ────────────────────────────────────────
    t_start = max(times_a[0], times_b[0])
    t_end   = min(times_a[-1], times_b[-1])

    if t_end <= t_start:
        st.error(
            "Signals have no overlapping time window. "
            "For accurate coupling analysis, capture both signals with the same trigger."
        )
        st.stop()

    # ── 2. Build common time grid and interpolate ─────────────────────────
    N_GRID   = min(20_000, len(times_a), len(times_b))
    t_common = np.linspace(t_start, t_end, N_GRID)
    dt       = (t_end - t_start) / N_GRID  # seconds per grid point

    v_a = np.interp(t_common, times_a, voltages_a)
    v_b = np.interp(t_common, times_b, voltages_b)

    # ── 3. Align at first transition if requested ─────────────────────────
    if align_method.startswith("Align"):
        thresh_a = sig_a["threshold"]
        thresh_b = sig_b["threshold"]
        bits_raw_a = (v_a >= thresh_a).astype(int)
        bits_raw_b = (v_b >= thresh_b).astype(int)

        trans_a = np.where(np.diff(bits_raw_a) != 0)[0]
        trans_b = np.where(np.diff(bits_raw_b) != 0)[0]

        if len(trans_a) > 0 and len(trans_b) > 0:
            shift = int(trans_a[0]) - int(trans_b[0])
            if shift > 0:
                v_b = np.roll(v_b, shift)
                v_b[:shift] = v_b[shift]
            elif shift < 0:
                v_a = np.roll(v_a, -shift)
                v_a[:-shift] = v_a[-shift]

    # ── 4. Normalize both signals to 0–1 ──────────────────────────────────
    def norm01(v):
        lo, hi = v.min(), v.max()
        return (v - lo) / (hi - lo + 1e-12)

    n_a = norm01(v_a)
    n_b = norm01(v_b)

    # Digital bits at 0.5 threshold
    bits_a = (n_a >= 0.5).astype(int)
    bits_b = (n_b >= 0.5).astype(int)

    # ── 5. Coupling efficiency ────────────────────────────────────────────
    if anti_phase:
        # Correctly coupled = A XOR B == 1  (one high, one low)
        correct_mask = bits_a != bits_b
    else:
        # Correctly coupled = A == B  (both same level)
        correct_mask = bits_a == bits_b

    coupling_pct = correct_mask.mean() * 100

    # Violation windows: where coupling fails
    violation_mask = ~correct_mask

    # ── 6. Transition skew ────────────────────────────────────────────────
    edges_a = np.where(np.diff(bits_a) != 0)[0]
    edges_b = np.where(np.diff(bits_b) != 0)[0]

    skews_us = []
    if len(edges_a) > 0 and len(edges_b) > 0:
        for ea in edges_a:
            nearest = edges_b[np.argmin(np.abs(edges_b - ea))]
            skews_us.append(abs(int(ea) - int(nearest)) * dt * 1e6)

    avg_skew = float(np.mean(skews_us)) if skews_us else 0.0
    max_skew = float(np.max(skews_us))  if skews_us else 0.0

    # ── 7. Cross-correlation (phase relationship) ─────────────────────────
    # Downsample for speed
    ds = max(1, N_GRID // 4000)
    ca = n_a[::ds] - 0.5
    cb = n_b[::ds] - 0.5
    corr      = np.correlate(ca, cb, mode="full")
    lags      = np.arange(-len(cb) + 1, len(ca)) * ds * dt * 1e3   # in ms
    norm_denom = np.sqrt(np.dot(ca, ca) * np.dot(cb, cb)) + 1e-12
    corr_norm  = corr / norm_denom

    peak_idx  = int(np.argmax(np.abs(corr_norm)))
    peak_lag  = float(lags[peak_idx])
    peak_val  = float(corr_norm[peak_idx])

    # Negative peak → anti-phase, positive → in-phase
    detected_rel = "Anti-phase" if peak_val < 0 else "In-phase"
    expected_rel  = "Anti-phase" if anti_phase else "In-phase"
    rel_match     = detected_rel == expected_rel

    # ── 8. Score label ────────────────────────────────────────────────────
    if coupling_pct >= 95:
        grade, grade_color = "Excellent", "#2e7d32"
    elif coupling_pct >= 80:
        grade, grade_color = "Good",      "#f57f17"
    elif coupling_pct >= 60:
        grade, grade_color = "Fair",      "#e65100"
    else:
        grade, grade_color = "Poor",      "#b71c1c"

    # ── 9. Display metrics ────────────────────────────────────────────────
    st.markdown(
        f"<div style='display:inline-block; padding:0.4rem 1.2rem; "
        f"background:{grade_color}; color:white; border-radius:0.5rem; "
        f"font-size:1.2rem; font-weight:700; margin-bottom:1rem;'>"
        f"Coupling: {coupling_pct:.1f}% — {grade}"
        f"</div>",
        unsafe_allow_html=True,
    )

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Coupling efficiency",  f"{coupling_pct:.1f}%")
    m2.metric("Avg transition skew",  f"{avg_skew:.2f} µs")
    m3.metric("Max transition skew",  f"{max_skew:.2f} µs")
    m4.metric("Detected relationship", detected_rel)
    m5.metric("Peak lag",             f"{peak_lag:.3f} ms",
              delta="✓ matches" if rel_match else "✗ mismatch",
              delta_color="normal" if rel_match else "inverse")

    if not rel_match:
        st.warning(
            f"Expected **{expected_rel}** but detected **{detected_rel}**. "
            "Check signal polarity or try toggling 'Invert signals'."
        )

    # ── 10. Violation chart ───────────────────────────────────────────────
    st.markdown("**Coupling violations** — shaded regions show where the signals are NOT correctly coupled.")

    fig_v = go.Figure()
    ds_plot = max(1, N_GRID // MAX_PTS)
    t_ms_c  = t_common[::ds_plot] * 1e3

    fig_v.add_trace(go.Scatter(
        x=t_ms_c, y=n_a[::ds_plot],
        mode="lines", name="A (normalised)",
        line=dict(color=COLORS["A"], width=1.2),
    ))
    fig_v.add_trace(go.Scatter(
        x=t_ms_c, y=n_b[::ds_plot],
        mode="lines", name="B (normalised)",
        line=dict(color=COLORS["B"], width=1.2),
    ))

    # Shade violation regions
    viol_ds  = violation_mask[::ds_plot]
    in_viol  = False
    v_start  = None
    for i, bad in enumerate(viol_ds):
        if bad and not in_viol:
            v_start = t_ms_c[i]
            in_viol = True
        elif not bad and in_viol:
            fig_v.add_vrect(x0=v_start, x1=t_ms_c[i],
                            fillcolor="red", opacity=0.18, line_width=0)
            in_viol = False
    if in_viol:
        fig_v.add_vrect(x0=v_start, x1=t_ms_c[-1],
                        fillcolor="red", opacity=0.18, line_width=0)

    fig_v.update_layout(
        xaxis_title="Time (ms)", yaxis_title="Normalised level (0–1)",
        margin=dict(l=0, r=0, t=10, b=0), height=280,
        legend=dict(orientation="h"),
        paper_bgcolor=pc["bg"], plot_bgcolor=pc["bg"], font=dict(color=pc["text"]),
        xaxis=dict(rangeslider=dict(visible=True, thickness=0.08), gridcolor=pc["grid"]),
        yaxis=dict(gridcolor=pc["grid"]),
    )
    st.plotly_chart(fig_v, use_container_width=True)

    # ── 11. Cross-correlation chart ───────────────────────────────────────
    with st.expander("Cross-correlation detail"):
        st.caption(
            "Shows how similar Signal A and Signal B are at every possible time lag. "
            "For a perfect anti-phase pair the peak is at −1.0; for in-phase it is +1.0. "
            "The lag at the peak shows any timing offset between the signals."
        )
        fig_cc = go.Figure()
        fig_cc.add_trace(go.Scatter(
            x=lags, y=corr_norm,
            mode="lines", name="Cross-correlation",
            line=dict(color="#9c27b0", width=1.2),
        ))
        fig_cc.add_vline(x=peak_lag, line=dict(color="red", dash="dash", width=1),
                         annotation_text=f"Peak {peak_val:.3f} @ {peak_lag:.3f} ms",
                         annotation_position="top right")
        fig_cc.add_hline(y=0, line=dict(color=pc["grid"], width=1))
        fig_cc.update_layout(
            xaxis_title="Lag (ms)", yaxis_title="Normalised correlation",
            yaxis_range=[-1.1, 1.1],
            margin=dict(l=0, r=0, t=10, b=0), height=240,
            paper_bgcolor=pc["bg"], plot_bgcolor=pc["bg"], font=dict(color=pc["text"]),
            xaxis=dict(gridcolor=pc["grid"]),
            yaxis=dict(gridcolor=pc["grid"]),
        )
        st.plotly_chart(fig_cc, use_container_width=True)

    # ── 12. Per-transition skew table ─────────────────────────────────────
    if skews_us:
        with st.expander("Per-transition skew table"):
            n_show = min(len(skews_us), 50)
            df_skew = pd.DataFrame({
                "Transition #":     list(range(1, n_show + 1)),
                "Time A (ms)":      [f"{edges_a[i] * dt * 1e3:.4f}"
                                     for i in range(n_show)],
                "Skew (µs)":        [f"{s:.2f}" for s in skews_us[:n_show]],
                "Status":           ["✓ OK" if s < (1e6 / sig_a["baud"] * 0.1)
                                     else "⚠ Skewed"
                                     for s in skews_us[:n_show]],
            })
            st.dataframe(df_skew, use_container_width=True, hide_index=True)
