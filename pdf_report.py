"""
Generates a formatted PDF report from decoded oscilloscope data.
"""

from datetime import date
from fpdf import FPDF


# Colours
C_DARK   = (15,  23,  42)   # title / section headers
C_MID    = (51,  65,  85)   # sub-labels
C_LIGHT  = (241, 245, 249)  # row fill (light)
C_WHITE  = (255, 255, 255)
C_ACCENT = (30,  100, 200)  # header bar


class ReportPDF(FPDF):
    def __init__(self, filename: str):
        super().__init__()
        self.filename = filename
        self.set_margins(18, 18, 18)
        self.set_auto_page_break(auto=True, margin=18)

    # ── header/footer ──────────────────────────────────────────────────────
    def header(self):
        self.set_fill_color(*C_ACCENT)
        self.rect(0, 0, 210, 12, "F")
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*C_WHITE)
        self.set_xy(8, 2)
        self.cell(0, 8, "PULSE-A  |  Oscilloscope Payload Decoder", align="L")
        self.set_xy(-55, 2)
        self.cell(47, 8, f"Page {self.page_no()}", align="R")
        self.set_text_color(*C_DARK)
        self.ln(6)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*C_MID)
        self.cell(0, 8, f"Generated {date.today()}  |  {self.filename}", align="C")

    # ── helpers ────────────────────────────────────────────────────────────
    def section_title(self, title: str):
        self.ln(4)
        self.set_fill_color(*C_DARK)
        self.set_text_color(*C_WHITE)
        self.set_font("Helvetica", "B", 10)
        self.cell(0, 8, f"  {title}", fill=True, ln=True)
        self.set_text_color(*C_DARK)
        self.ln(2)

    def kv_table(self, rows: list[tuple[str, str]], cols: int = 2):
        """Render key-value pairs in a grid of `cols` columns."""
        col_w = (self.epw) / cols
        half  = col_w / 2

        for i, (k, v) in enumerate(rows):
            if i % cols == 0 and i > 0:
                self.ln(0)
            fill = (i // cols) % 2 == 0
            bg   = C_LIGHT if fill else C_WHITE
            self.set_fill_color(*bg)

            x = self.get_x()
            y = self.get_y()
            # label
            self.set_font("Helvetica", "B", 8)
            self.set_text_color(*C_MID)
            self.cell(half, 7, f" {k}", fill=True)
            # value
            self.set_font("Helvetica", "", 8)
            self.set_text_color(*C_DARK)
            self.cell(half, 7, str(v), fill=True)
            if (i + 1) % cols == 0:
                self.ln()

        if len(rows) % cols != 0:
            self.ln()
        self.ln(2)

    def mono_block(self, text: str, font_size: int = 7):
        """Render a monospace block (bit stream, hex dump, decoded text)."""
        self.set_font("Courier", "", font_size)
        self.set_fill_color(*C_LIGHT)
        self.set_text_color(*C_DARK)
        # split into lines and print each
        for line in text.splitlines():
            # multi_cell wraps if line is too long
            self.multi_cell(0, 5, line, fill=True)
        self.ln(2)


# ── public function ────────────────────────────────────────────────────────

def build_pdf(
    filename: str,
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
) -> bytes:
    pdf = ReportPDF(filename)
    pdf.add_page()

    # ── Title ──────────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*C_DARK)
    pdf.ln(2)
    pdf.cell(0, 12, "Oscilloscope Payload Report", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*C_MID)
    pdf.cell(0, 6, f"File: {filename}    Generated: {date.today()}", ln=True)
    pdf.ln(2)

    # ── Oscilloscope metadata ──────────────────────────────────────────────
    if meta:
        pdf.section_title("Capture Metadata")
        meta_labels = {
            "record_length":    "Record length",
            "sample_rate":      "Sample rate (Hz)",
            "vertical_scale":   "Vertical scale",
            "vertical_offset":  "Vertical offset",
            "horizontal_scale": "Horizontal scale",
        }
        rows = [(meta_labels[k], meta[k]) for k in meta_labels if k in meta]
        pdf.kv_table(rows, cols=2)

    # ── Signal analysis ────────────────────────────────────────────────────
    duration = times[-1] - times[0]
    pdf.section_title("Signal Analysis")
    pdf.kv_table([
        ("Samples",          f"{len(voltages):,}"),
        ("Duration",         f"{duration*1e3:.4f} ms"),
        ("Voltage min",      f"{min(voltages):.3f} V"),
        ("Voltage max",      f"{max(voltages):.3f} V"),
        ("Threshold",        f"{threshold:.3f} V"),
        ("Signal polarity",  "Inverted (active-low)" if inverted else "Normal (active-high)"),
    ], cols=2)

    # ── Bit extraction ─────────────────────────────────────────────────────
    pdf.section_title("Bit Extraction")
    pdf.kv_table([
        ("Baud rate",      f"{baud:,.1f} bps"),
        ("Bit period",     f"{1/baud*1e6:.3f} us"),
        ("Bits extracted", str(len(bit_stream))),
        ("Bits per frame", str(bits_per_frame)),
        ("Bit order",      "LSB first" if lsb_first else "MSB first"),
        ("Frames decoded", str(len(frames))),
    ], cols=2)

    # ── Raw bit stream ─────────────────────────────────────────────────────
    pdf.section_title("Raw Bit Stream")
    stream_str = "".join(str(b) for b in bit_stream)
    lines = []
    for i in range(0, len(stream_str), 64):
        chunk = stream_str[i : i + 64]
        lines.append(" ".join(chunk[j : j + 8] for j in range(0, len(chunk), 8)))
    pdf.mono_block("\n".join(lines), font_size=7)

    # ── Decoded payload ────────────────────────────────────────────────────
    pdf.section_title(f"Decoded Payload ({encoding.upper()})")
    if encoding == "ascii":
        payload_text = "".join(decoded)
        # wrap at 80 chars
        wrapped = "\n".join(payload_text[i : i + 80] for i in range(0, len(payload_text), 80))
        pdf.mono_block(wrapped, font_size=8)
    else:
        rows_out = []
        for i in range(0, len(decoded), 16):
            rows_out.append(" ".join(decoded[i : i + 16]))
        pdf.mono_block("\n".join(rows_out), font_size=7)

    # ── Hex dump ───────────────────────────────────────────────────────────
    pdf.section_title("Hex Dump")
    hex_lines = []
    for i in range(0, len(frames), 16):
        row      = frames[i : i + 16]
        addr     = f"{i:04X}"
        hex_part = " ".join(f"{v:02X}" for v in row)
        asc_part = "".join(chr(v) if 32 <= v <= 126 else "." for v in row)
        hex_lines.append(f"{addr}  {hex_part:<48}  {asc_part}")
    pdf.mono_block("\n".join(hex_lines), font_size=7)

    return bytes(pdf.output())
