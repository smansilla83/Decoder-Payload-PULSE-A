"""
Shared theme helpers — import in every page to keep dark/light consistent.
"""

import streamlit as st

# ---------------------------------------------------------------------------
# CSS blocks
# ---------------------------------------------------------------------------

_WARM_CSS = """
<style>
  /* ── Warm beige palette ────────────────────────────────────────────
     bg:       #faf6f0  warm cream
     sidebar:  #f0ebe0  warm linen
     surface:  #ede6d8  inputs / cards / dropzone
     surface2: #e4dccb  hover / deeper surface
     border:   #c8b89a  caramel border
     text:     #2c1f0e  dark espresso brown
     muted:    #6b5540  warm medium brown
  ─────────────────────────────────────────────────────────────────── */

  html, body, .stApp, .main, .block-container {
    background-color: #faf6f0 !important;
  }
  [data-testid="stSidebar"],
  [data-testid="stSidebar"] > div:first-child {
    background-color: #f0ebe0 !important;
  }

  /* Text */
  .stApp, .stApp p, .stApp span, .stApp div,
  .stApp label, .stApp h1, .stApp h2, .stApp h3,
  .stApp h4, .stApp h5, .stApp h6, .stApp li,
  [data-testid="stSidebar"] * {
    color: #2c1f0e !important;
  }

  /* File uploader — every selector variant */
  [data-testid="stFileUploader"],
  [data-testid="stFileUploader"] > div,
  section[data-testid="stFileUploadDropzone"],
  div[data-testid="stFileUploadDropzone"],
  [data-testid="stFileUploadDropzone"],
  [data-testid="stFileUploadDropzone"] > div {
    background-color: #ede6d8 !important;
    border-color: #c8b89a !important;
  }
  [data-testid="stFileUploadDropzone"] *,
  [data-testid="stFileUploader"] * {
    color: #2c1f0e !important;
    background-color: transparent !important;
  }
  [data-testid="stFileUploadDropzone"] button {
    background-color: #e4dccb !important;
    border-color: #c8b89a !important;
    color: #2c1f0e !important;
  }

  /* Selects / dropdowns */
  [data-baseweb="select"] > div,
  [data-baseweb="select"] div[class*="ValueContainer"],
  [data-baseweb="input"] > div,
  [data-baseweb="base-input"],
  [data-baseweb="select"] * {
    background-color: #ede6d8 !important;
    border-color: #c8b89a !important;
    color: #2c1f0e !important;
  }
  [data-baseweb="popover"] div,
  [data-baseweb="menu"] {
    background-color: #ede6d8 !important;
    color: #2c1f0e !important;
  }
  [data-baseweb="option"]:hover { background-color: #e4dccb !important; }

  /* Inputs */
  input[type="number"], input[type="text"] {
    background-color: #ede6d8 !important;
    color: #2c1f0e !important;
    border-color: #c8b89a !important;
  }

  /* Buttons */
  button, [data-testid="stBaseButton-secondary"] {
    background-color: #e4dccb !important;
    color: #2c1f0e !important;
    border-color: #c8b89a !important;
  }

  /* Alerts */
  [data-testid="stAlert"], [data-testid="stAlertContainer"] {
    background-color: #eee6d5 !important;
    border-left-color: #c8b89a !important;
  }
  [data-testid="stAlert"] * { color: #2c1f0e !important; }

  /* Metrics */
  [data-testid="stMetricValue"] { color: #2c1f0e !important; }
  [data-testid="stMetricLabel"] { color: #6b5540 !important; }

  /* Tabs */
  [data-baseweb="tab-list"]  { background-color: #e4dccb !important; }
  [data-baseweb="tab"]       { color: #2c1f0e !important; }
  [aria-selected="true"]     { background-color: #d4c8b0 !important; }
  [data-baseweb="tab-panel"] { background-color: #faf6f0 !important; }

  /* Code */
  pre, code, [data-testid="stCode"] pre, .stCodeBlock, .stCodeBlock * {
    background-color: #ede6d8 !important;
    color: #2c1f0e !important;
  }

  /* Expanders */
  [data-testid="stExpander"],
  [data-testid="stExpander"] > details {
    background-color: #f0ebe0 !important;
    border-color: #c8b89a !important;
  }
  [data-testid="stExpander"] summary { color: #2c1f0e !important; }

  /* Dataframe */
  [data-testid="stDataFrame"] *,
  [data-testid="stDataFrameResizable"] * {
    background-color: #ede6d8 !important;
    color: #2c1f0e !important;
  }

  /* Divider */
  hr { border-color: #c8b89a !important; }

  /* Caption */
  .stCaption, [data-testid="stCaptionContainer"] * { color: #6b5540 !important; }

  /* Nav page links */
  [data-testid="stPageLink"] a,
  [data-testid="stPageLink"] a * { color: #2c1f0e !important; }
  [data-testid="stPageLink-active"] a { background-color: #d4c8b0 !important; }
</style>
"""

_PRINT_CSS = """
<style>
@media print {
    [data-testid="stSidebar"],
    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    [data-testid="stFileUploader"],
    section[data-testid="stFileUploadDropzone"],
    .stDownloadButton, .stButton, footer { display: none !important; }
    .block-container { padding: 1rem !important; }
}
</style>
"""

# ---------------------------------------------------------------------------
# Plot colours (expose so pages can use them for Plotly)
# ---------------------------------------------------------------------------

def plot_colors(light: bool) -> dict:
    if light:
        return dict(bg="#ede6d8", text="#2c1f0e", grid="#c8b89a")
    return dict(bg="#0e1117", text="#fafafa", grid="#333333")


# ---------------------------------------------------------------------------
# Helpers called from each page
# ---------------------------------------------------------------------------

def get_light() -> bool:
    return st.session_state.get("light_mode", False)


def apply_theme():
    """Inject theme + print CSS. Call right after set_page_config."""
    light = get_light()
    st.markdown(_PRINT_CSS + (_WARM_CSS if light else ""), unsafe_allow_html=True)
    return light


def render_nav(page_key: str = "main"):
    """
    Render the top nav bar (Decoder / Compare / Reference) with the
    dark/light toggle. page_key must be unique per page to avoid key
    conflicts in session state.
    """
    if "light_mode" not in st.session_state:
        st.session_state.light_mode = False

    light = get_light()
    nav1, nav2, nav3, _, theme_col = st.columns([1, 1, 1, 4, 1])
    with nav1:
        st.page_link("app.py", label="🏠 Decoder")
    with nav2:
        st.page_link("pages/Compare.py", label="🔀 Compare")
    with nav3:
        st.page_link("pages/Reference.py", label="📖 Reference")
    with theme_col:
        if st.button("☀️ Light" if not light else "🌙 Dark", key=f"theme_{page_key}"):
            st.session_state.light_mode = not light
            st.rerun()
    st.divider()
