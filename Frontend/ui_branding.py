from pathlib import Path
import base64
import streamlit as st
from textwrap import dedent

def page_header(title: str, subtitle: str | None = None, logo: str = "logo.png"):
    HERE = Path(__file__).resolve().parent
    logo_path = HERE / "assets" / logo

    logo_html = ""
    if logo_path.exists():
        b64 = base64.b64encode(logo_path.read_bytes()).decode("utf-8")
        logo_html = f"<img src='data:image/png;base64,{b64}' style='width:56px;height:56px;object-fit:contain;flex:0 0 56px;' />"

    subtitle_html = f"<div style='font-size:1.05rem;opacity:.75;margin-top:2px;'>{subtitle}</div>" if subtitle else ""

    st.markdown(
        dedent("""
        <style>
          .bb-header{display:flex;align-items:center;gap:14px;margin:6px 0 10px 0;}
          .bb-title{font-size:2.6rem;font-weight:800;line-height:1.1;margin:0;}
          .bb-header-text{min-width:0;}
          @media (max-width:900px){ .bb-title{font-size:2.0rem;} }
        </style>
        """),
        unsafe_allow_html=True,
    )

    st.markdown(
        dedent(f"""
        <div class="bb-header">
          {logo_html}
          <div class="bb-header-text">
            <div class="bb-title">{title}</div>
            {subtitle_html}
          </div>
        </div>
        """),
        unsafe_allow_html=True,
    )

def apply_branding():
    here = Path(__file__).resolve().parent
    logo_path = here / "assets" / "logo.png"

    if logo_path.exists():
        b64 = base64.b64encode(logo_path.read_bytes()).decode("utf-8")

        st.sidebar.markdown(
            f"""
            <div style="text-align:center; margin-top: 6px; margin-bottom: 10px;">
                <img src="data:image/png;base64,{b64}" width="80" />
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.sidebar.warning(f"Logo not found: {logo_path}")

    st.sidebar.markdown(
        "<div style='text-align:center; font-weight:700; font-size:20px;'>ByteBrains</div>",
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        "<div style='text-align:center; opacity:0.75; margin-top:-6px;'>AI Meeting Assistant</div>",
        unsafe_allow_html=True,
    )

    st.markdown("""
    <style>
    /* Header layout */
    .bb-header{
    display:flex;
    align-items:center;
    gap:14px;
    margin-top: 6px;
    margin-bottom: 10px;
    }
    .bb-title{
    font-size: 2.6rem;        /* adjust */
    font-weight: 800;
    line-height: 1.1;
    margin: 0;
    }
    .bb-header-text{
    min-width: 0;
    }
    @media (max-width: 900px){
    .bb-title{ font-size: 2.0rem; }
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <style>
    /* --- Primary button gradient --- */
    button[kind="primary"] {
    background: linear-gradient(90deg, #8B5CF6 0%, #22C3EE 100%) !important;
    border: 0 !important;
    }
    button[kind="primary"]:hover {
    filter: brightness(0.98);
    transform: translateY(-1px);
    }

    /* Disabled primary shouldn't look "active" */
    button[kind="primary"][disabled] {
    opacity: 0.35 !important;
    filter: grayscale(0.8) !important;
    transform: none !important;
    cursor: not-allowed !important;
    }

    /* --- Subtle "premium" cards/containers --- */
    div[data-testid="stContainer"][data-border="true"] {
    border-radius: 16px;
    border: 1px solid rgba(15, 23, 42, 0.08);
    background: rgba(255, 255, 255, 0.70);
    box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
    }

    /* --- Sidebar polish --- */
    section[data-testid="stSidebar"] {
    border-right: 1px solid rgba(15, 23, 42, 0.08);
    }
    section[data-testid="stSidebar"]::before {
    content: "";
    display: block;
    height: 4px;
    background: linear-gradient(90deg, #8B5CF6, #22C3EE);
    }

    /* Center sidebar logo image */
    section[data-testid="stSidebar"] img {
    display: block;
    margin: 0 auto;
    }
    </style>
    """, unsafe_allow_html=True)