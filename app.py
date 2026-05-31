"""
app.py
------
Enterprise fintech dashboard — Lucknow Artisan Alternative Credit Scoring System.

Run:      streamlit run app.py
Requires: artisan_credit.db  (python3 main.py first)
Packages: streamlit, plotly, pandas, numpy
"""

import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from artisan_credit.agent_router import route_artisan
from artisan_credit.data_generator import MONTHLY_SEASONALITY
from artisan_credit.scoring_engine import CreditProfile, score_artisan
from language_parser import ParsedStatement, parse_trade_statement

DB_PATH = "artisan_credit.db"

# ──────────────────────────────────────────────────────────────────────────────
# Page config  (must be the very first Streamlit call)
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Artisan Credit Intelligence",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────────────────────────────────────
# Global CSS — dark fintech theme
# ──────────────────────────────────────────────────────────────────────────────
_kc_dark = st.session_state.get("kc_dark", True)
_theme_vars = """
  --bg:#0c0e13; --surface:#14171e; --surface-2:#191d25; --surface-3:#1e222b;
  --ink:#eef1f6; --ink-2:#b8bec9; --muted:#7e8693; --faint:#5c636f;
  --border:#262b34; --border-2:#20242c; --grid:#222730;
  --t-prime:#33b07e; --t-strong:#82c64f; --t-std:#e3b745; --t-watch:#f0993f; --t-sub:#ef6d6d;
  --accent:#4f46d6;
  --shadow:0 1px 2px rgba(0,0,0,.3), 0 6px 22px rgba(0,0,0,.35);
  --shadow-sm:0 1px 2px rgba(0,0,0,.35);
""" if _kc_dark else """
  --bg:#f1f1ec; --surface:#ffffff; --surface-2:#faf9f6; --surface-3:#f4f3ef;
  --ink:#15171c; --ink-2:#3c424d; --muted:#878d99; --faint:#aeb3bd;
  --border:#e5e4de; --border-2:#eeede8; --grid:#ecebe5;
  --t-prime:#157f55; --t-strong:#5d9b2f; --t-std:#c2901f; --t-watch:#d9772a; --t-sub:#c93f3f;
  --accent:#4f46d6;
  --shadow:0 1px 2px rgba(20,23,28,.04), 0 4px 16px rgba(20,23,28,.05);
  --shadow-sm:0 1px 2px rgba(20,23,28,.05);
"""

# Inject CSS tokens (f-string for theme vars) + font import
st.markdown(
    f"<style>"
    f"@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700"
    f"&family=IBM+Plex+Mono:wght@400;500;600"
    f"&family=Noto+Sans+Devanagari:wght@400;500;600;700&display=swap');"
    f"body {{ {_theme_vars} }}"
    f"html,body {{ font-family:'IBM Plex Sans','Noto Sans Devanagari',system-ui,sans-serif;"
    f"-webkit-font-smoothing:antialiased; }}"
    f"</style>",
    unsafe_allow_html=True,
)

# Main component CSS (plain string — no f-string needed)
st.markdown("""
<style>
/* ── Base ─────────────────────────────────────────────────────────── */
[data-testid="stAppViewContainer"],
[data-testid="stMain"] { background: var(--bg) !important; }
.block-container { padding-top: 1.2rem !important; padding-bottom: 1rem; max-width: 1440px; }

/* ── Sidebar ─────────────────────────────────────────────────────── */
[data-testid="stSidebar"]          { background: var(--surface) !important; border-right: 1px solid var(--border); }
[data-testid="stSidebar"] *        { color: var(--ink-2) !important; font-family: 'IBM Plex Sans', system-ui, sans-serif !important; }
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] strong   { color: var(--ink) !important; }
[data-testid="stSidebar"] .stMarkdown p { font-size: 0.82rem; }
[data-testid="stSidebar"] [data-testid="stMetricValue"]  { color: var(--accent) !important; font-size: 1rem !important; font-family: 'IBM Plex Mono', monospace !important; }
[data-testid="stSidebar"] [data-testid="stMetricLabel"]  { color: var(--muted) !important; }

/* ── Tab strip ───────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"]  {
    background: transparent !important;
    border-bottom: 1px solid var(--border) !important;
    gap: 0.15rem;
    padding-bottom: 0;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: var(--muted) !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.04em;
    font-family: 'IBM Plex Sans', sans-serif !important;
    border-radius: 6px 6px 0 0 !important;
    padding: 0.55rem 1.1rem !important;
    border-bottom: 2px solid transparent !important;
}
.stTabs [aria-selected="true"] {
    color: var(--accent) !important;
    border-bottom: 2px solid var(--accent) !important;
    background: color-mix(in srgb, var(--accent) 5%, transparent) !important;
}
.stTabs [data-baseweb="tab-panel"] { padding-top: 1rem; }

/* ── Progress bar ────────────────────────────────────────────────── */
.stProgress > div                  { background: var(--surface-3) !important; border-radius: 9999px; height: 7px !important; }
.stProgress > div > div            { background: var(--accent) !important; border-radius: 9999px; }

/* ── Metric delta hide ───────────────────────────────────────────── */
[data-testid="stMetricDelta"] svg  { display:none; }

/* ── Expander ─────────────────────────────────────────────────────── */
[data-testid="stExpander"]         { background: var(--surface) !important; border: 1px solid var(--border) !important; border-radius: 10px !important; }
[data-testid="stExpander"] summary { color: var(--muted) !important; font-size: 0.78rem; }

/* ── Code block ───────────────────────────────────────────────────── */
.stCodeBlock code { font-size: 0.72rem !important; font-family: 'IBM Plex Mono', monospace !important; }

/* ─────────────────────────────────────────────────────────────────────────
   LAYOUT PRIMITIVES
───────────────────────────────────────────────────────────────────────── */
.section-header {
    font-size: 0.62rem; font-weight: 700; letter-spacing: 0.14em;
    text-transform: uppercase; color: var(--muted);
    padding-bottom: 0.5rem; margin-bottom: 0.75rem;
    border-bottom: 1px solid var(--border);
}

.fin-card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 11px; padding: 1.25rem 1.5rem;
}

/* ─────────────────────────────────────────────────────────────────────────
   KARIGAR CRED BRAND HEADER
───────────────────────────────────────────────────────────────────────── */
.kc-brand-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 12px 18px; background: var(--surface);
    border: 1px solid var(--border); border-radius: 11px;
    margin-bottom: 14px; box-shadow: var(--shadow-sm);
    font-family: 'IBM Plex Sans', sans-serif;
}
.kc-brand-left { display: flex; align-items: center; gap: 11px; }
.kc-brand-logo {
    width: 34px; height: 34px; border-radius: 9px;
    background: var(--accent); display: grid; place-items: center;
    color: #fff; font-size: 17px; line-height: 1; box-shadow: var(--shadow-sm);
}
.kc-brand-name { font-weight: 700; font-size: 16px; letter-spacing: -0.2px; color: var(--ink); }
.kc-brand-sub  { font-size: 10px; color: var(--muted); letter-spacing: 0.4px; text-transform: uppercase; margin-top: 1px; }
.kc-env-pill {
    display: flex; align-items: center; gap: 7px;
    font-size: 11.5px; color: var(--muted); font-family: 'IBM Plex Mono', monospace;
}
.kc-env-dot {
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--t-prime);
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--t-prime) 22%, transparent);
}
.kc-env-sep { color: var(--faint); }
.kc-header-right { display: flex; align-items: center; gap: 12px; }
.kc-dark-toggle {
    width: 32px; height: 32px; border-radius: 8px;
    border: 1px solid var(--border); background: var(--surface-2);
    color: var(--ink-2); display: grid; place-items: center; cursor: pointer;
    font-size: 14px;
}
.kc-user-chip { display: flex; align-items: center; gap: 9px; }
.kc-user-av {
    width: 30px; height: 30px; border-radius: 8px;
    background: var(--surface-3); border: 1px solid var(--border);
    display: grid; place-items: center; font-size: 11px;
    font-weight: 700; color: var(--ink-2); font-family: 'IBM Plex Mono', monospace;
}
.kc-user-name { font-size: 13px; font-weight: 600; color: var(--ink); line-height: 1.1; }
.kc-user-role { font-size: 10.5px; color: var(--muted); }

/* ─────────────────────────────────────────────────────────────────────────
   COHORT STRIP
───────────────────────────────────────────────────────────────────────── */
.kc-cohort {
    display: grid; grid-template-columns: repeat(5, minmax(0,1fr)) minmax(200px,1.5fr);
    gap: 1px; background: var(--border); border: 1px solid var(--border);
    border-radius: 11px; overflow: hidden; margin-bottom: 14px;
    box-shadow: var(--shadow-sm);
}
.kc-cohort-cell { background: var(--surface); padding: 12px 15px; }
.kc-cohort-v {
    font-family: 'IBM Plex Mono', monospace; font-size: 20px; font-weight: 600;
    letter-spacing: -0.5px; color: var(--ink);
}
.kc-cohort-k { font-size: 11px; font-weight: 600; color: var(--ink-2); margin-top: 3px; }
.kc-cohort-s { font-size: 10.5px; color: var(--muted); margin-top: 1px; }
.kc-cohort-cov { background: var(--surface); padding: 11px 15px; }
.kc-cohort-cov-k { font-size: 11px; font-weight: 600; color: var(--ink-2); margin-bottom: 8px; }
.kc-cov-track { height: 5px; border-radius: 3px; background: var(--surface-3); overflow: hidden; margin-bottom: 2px; }
.kc-cov-fill  { height: 100%; border-radius: 3px; }
.kc-cov-lab   { display: flex; justify-content: space-between; font-size: 10.5px; color: var(--muted); margin-bottom: 6px; }
.kc-cov-lab .mono { font-family: 'IBM Plex Mono', monospace; }

/* ─────────────────────────────────────────────────────────────────────────
   SUBJECT BAR
───────────────────────────────────────────────────────────────────────── */
.kc-subject {
    display: flex; align-items: center; justify-content: space-between; gap: 16px;
    padding: 6px 2px; margin-bottom: 12px;
}
.kc-subject-name {
    font-size: 23px; font-weight: 700; letter-spacing: -0.5px; color: var(--ink);
    font-family: 'IBM Plex Sans', sans-serif;
}
.kc-subject-chips { display: flex; gap: 7px; margin-top: 6px; flex-wrap: wrap; }
.kc-chip {
    font-size: 11px; color: var(--ink-2); background: var(--surface);
    border: 1px solid var(--border); border-radius: 6px;
    padding: 3px 9px; font-weight: 500;
}
.kc-band-badge {
    display: flex; align-items: center; gap: 7px;
    font-size: 13px; font-weight: 600;
    padding: 7px 14px; border: 1.5px solid; border-radius: 9px;
    background: var(--surface); white-space: nowrap;
}
.kc-band-dot { width: 8px; height: 8px; border-radius: 50%; }

/* ─────────────────────────────────────────────────────────────────────────
   DASHBOARD HEADER BAR (legacy — now kc-subject)
───────────────────────────────────────────────────────────────────────── */
.dash-header {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 11px; padding: 1rem 1.4rem;
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 0.9rem;
}
.dash-header-name { font-size: 1.25rem; font-weight: 700; color: var(--ink); letter-spacing: -0.02em; }
.dash-header-sub  { font-size: 0.78rem; color: var(--muted); margin-top: 0.18rem; }
.dash-header-right { display: flex; align-items: center; gap: 0.65rem; }

/* ─────────────────────────────────────────────────────────────────────────
   DASHBOARD HEADER BAR
───────────────────────────────────────────────────────────────────────── */
.dash-header {
    background: linear-gradient(135deg,#1A1D24 0%,#22262F 100%);
    border: 1px solid #2E323D; border-radius: 12px;
    padding: 1.1rem 1.6rem;
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 0.9rem;
}
.dash-header-name {
    font-size: 1.3rem; font-weight: 800; color: #F1F5F9; letter-spacing: -0.02em;
}
.dash-header-sub {
    font-size: 0.78rem; color: #64748B; margin-top: 0.18rem;
}
.dash-header-right { display: flex; align-items: center; gap: 0.65rem; }

/* ─────────────────────────────────────────────────────────────────────────
   EXECUTIVE SUMMARY MATRIX
───────────────────────────────────────────────────────────────────────── */
.kc-exec {
    display: grid; grid-template-columns: repeat(6,1fr); gap: 1px;
    background: var(--border); border: 1px solid var(--border);
    border-radius: 11px; overflow: hidden; box-shadow: var(--shadow-sm);
    margin-bottom: 14px;
}
.kc-exec-cell { background: var(--surface); padding: 13px 15px; position: relative; }
.kc-exec-cell.accent::before {
    content: ""; position: absolute; left: 0; top: 0; bottom: 0;
    width: 3px; background: var(--accent);
}
.kc-exec-k {
    font-size: 10.5px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.4px; color: var(--muted);
}
.kc-exec-v {
    font-family: 'IBM Plex Mono', monospace; font-size: 24px;
    font-weight: 600; letter-spacing: -0.5px; margin-top: 7px; line-height: 1; color: var(--ink);
}
.kc-exec-s { font-size: 11px; color: var(--muted); margin-top: 5px; }

/* legacy exec-metric kept for compat */
.exec-metric {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 11px; padding: 1.2rem 1.4rem; text-align: center; height: 100%;
}
.exec-metric .em-label {
    font-size: 0.6rem; font-weight: 700; letter-spacing: 0.15em;
    text-transform: uppercase; color: var(--muted); margin-bottom: 0.55rem;
}
.exec-metric .em-value {
    font-family: 'IBM Plex Mono', monospace; font-size: 2rem; font-weight: 600;
    line-height: 1; letter-spacing: -0.03em; color: var(--ink);
}
.exec-metric .em-sub {
    font-size: 0.7rem; color: var(--muted); margin-top: 0.35rem;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

/* ─────────────────────────────────────────────────────────────────────────
   RISK BAND BADGES
───────────────────────────────────────────────────────────────────────── */
.risk-badge {
    display: inline-block; padding: 0.22rem 0.8rem;
    border-radius: 9999px; font-size: 0.65rem;
    font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase;
}
.risk-prime  { background: color-mix(in srgb,var(--t-prime) 13%,transparent); color: var(--t-prime); border: 1px solid color-mix(in srgb,var(--t-prime) 30%,transparent); }
.risk-strong { background: color-mix(in srgb,var(--t-strong) 13%,transparent); color: var(--t-strong); border: 1px solid color-mix(in srgb,var(--t-strong) 30%,transparent); }
.risk-std    { background: color-mix(in srgb,var(--t-std) 13%,transparent);    color: var(--t-std);   border: 1px solid color-mix(in srgb,var(--t-std) 30%,transparent); }
.risk-watch  { background: color-mix(in srgb,var(--t-watch) 13%,transparent);  color: var(--t-watch); border: 1px solid color-mix(in srgb,var(--t-watch) 30%,transparent); }
.risk-sub    { background: color-mix(in srgb,var(--t-sub) 13%,transparent);    color: var(--t-sub);   border: 1px solid color-mix(in srgb,var(--t-sub) 30%,transparent); }
/* legacy aliases */
.risk-near   { background: color-mix(in srgb,var(--t-strong) 13%,transparent); color: var(--t-strong); border: 1px solid color-mix(in srgb,var(--t-strong) 30%,transparent); }
.risk-deep   { background: color-mix(in srgb,var(--t-sub) 13%,transparent);    color: var(--t-sub);   border: 1px solid color-mix(in srgb,var(--t-sub) 30%,transparent); }
.risk-invis  { background: color-mix(in srgb,var(--accent) 12%,transparent);   color: var(--accent);  border: 1px solid color-mix(in srgb,var(--accent) 28%,transparent); }

/* ─────────────────────────────────────────────────────────────────────────
   SIGNAL DECOMPOSITION CARDS
───────────────────────────────────────────────────────────────────────── */
.kc-sig {
    background: var(--surface-2); border: 1px solid var(--border);
    border-radius: 9px; padding: 14px; height: 100%;
}
.kc-sig-top { display: flex; justify-content: space-between; align-items: center; }
.kc-sig-t   { font-size: 12px; font-weight: 600; color: var(--ink); }
.kc-sig-w   {
    font-size: 10.5px; color: var(--muted); font-family: 'IBM Plex Mono', monospace;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 5px; padding: 1px 6px;
}
.kc-sig-score { display: flex; align-items: baseline; gap: 3px; margin: 11px 0 12px; }
.kc-sig-v     { font-family: 'IBM Plex Mono', monospace; font-size: 30px; font-weight: 600; letter-spacing: -1px; color: var(--ink); }
.kc-sig-d     { font-size: 12px; color: var(--muted); }
.kc-sig-grade {
    margin-left: auto; font-size: 13px; font-weight: 700;
    width: 24px; height: 24px; border-radius: 6px;
    display: grid; place-items: center; color: #fff; align-self: center;
}
.kc-sig-grade[data-g="A"] { background: var(--t-prime); }
.kc-sig-grade[data-g="B"] { background: var(--t-strong); }
.kc-sig-grade[data-g="C"] { background: var(--t-std); }
.kc-sig-grade[data-g="D"] { background: var(--t-watch); }
.kc-sig-grade[data-g="E"] { background: var(--t-sub); }
.kc-sig-rows { display: flex; flex-direction: column; gap: 6px; border-top: 1px solid var(--border-2); padding-top: 10px; }
.kc-sig-r    { display: flex; justify-content: space-between; font-size: 11.5px; }
.kc-sig-r span:first-child { color: var(--muted); }
.kc-sig-r span:last-child  { color: var(--ink); font-weight: 600; font-family: 'IBM Plex Mono', monospace; }
/* legacy signal-card compat */
.signal-card {
    background: var(--surface-2); border: 1px solid var(--border);
    border-radius: 9px; padding: 14px; height: 100%;
}
.signal-label { font-size: 0.6rem; font-weight: 700; letter-spacing: 0.13em; text-transform: uppercase; color: var(--muted); margin-bottom: 0.4rem; }
.signal-score { font-family: 'IBM Plex Mono', monospace; font-size: 2rem; font-weight: 600; line-height: 1; letter-spacing: -0.03em; margin-bottom: 0.08rem; color: var(--ink); }
.signal-denom { font-size: 0.85rem; color: var(--muted); }
.signal-weight { font-size: 0.68rem; color: var(--faint); margin-bottom: 0.6rem; }
.signal-kv {
    display: flex; justify-content: space-between; font-size: 0.76rem; color: var(--muted);
    padding: 0.28rem 0; border-bottom: 1px solid var(--border-2);
}
.signal-kv:last-of-type { border-bottom: none; }
.signal-kv-val { font-weight: 700; font-family: 'IBM Plex Mono', monospace; color: var(--ink); }
.sig-grade { font-size: 0.6rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; padding: 0.12rem 0.45rem; border-radius: 4px; }

/* ─────────────────────────────────────────────────────────────────────────
   UNDERWRITING SUITE (right column)
───────────────────────────────────────────────────────────────────────── */
.kc-uw-panel {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 11px; box-shadow: var(--shadow); padding: 15px;
    display: flex; flex-direction: column; gap: 13px;
}
.kc-uw-hd {
    display: flex; align-items: center; justify-content: space-between;
    font-size: 12.5px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.5px; color: var(--ink-2);
}
.kc-uw-tag {
    font-size: 11px; font-weight: 600; border: 1.5px solid;
    border-radius: 6px; padding: 2px 8px;
}
.kc-scheme-block {
    border-radius: 10px; padding: 15px; overflow: hidden;
    background: color-mix(in srgb, var(--accent) 9%, var(--surface));
    border: 1px solid color-mix(in srgb, var(--accent) 28%, var(--border));
}
.kc-scheme-eyebrow { font-size: 10.5px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.6px; color: var(--accent); }
.kc-scheme-name  { font-size: 19px; font-weight: 700; letter-spacing: -0.3px; margin-top: 5px; color: var(--ink); }
.kc-scheme-amt   { font-family: 'IBM Plex Mono', monospace; font-size: 18px; font-weight: 600; margin-top: 7px; color: var(--ink); }
.kc-scheme-amt span { color: var(--muted); font-size: 13px; }
.kc-scheme-card  { font-size: 11.5px; color: var(--muted); margin-top: 7px; }
.kc-conf-row     { display: flex; justify-content: space-between; font-size: 11.5px; font-weight: 600; color: var(--ink-2); margin-bottom: 5px; }
.kc-conf-row span:last-child { font-family: 'IBM Plex Mono', monospace; color: var(--accent); }
.kc-conf-track   { height: 7px; background: var(--surface-3); border-radius: 4px; overflow: hidden; }
.kc-conf-fill    { height: 100%; background: var(--accent); border-radius: 4px; }
.kc-uw-sec       { font-size: 10.5px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: var(--muted); }
.kc-alt          { display: flex; align-items: center; gap: 9px; padding: 8px 10px; background: var(--surface-2); border: 1px solid var(--border); border-radius: 8px; margin-bottom: 5px; }
.kc-alt-dot      { width: 8px; height: 8px; border-radius: 50%; flex: none; }
.kc-alt-name     { font-size: 12.5px; font-weight: 500; flex: 1; color: var(--ink-2); }
.kc-alt-fit      { font-family: 'IBM Plex Mono', monospace; font-size: 12.5px; font-weight: 600; color: var(--muted); }
.kc-callouts-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 9px; }
.kc-callout      { border-radius: 9px; padding: 11px; border: 1px solid; }
.kc-callout--risk { background: color-mix(in srgb,var(--t-watch) 8%,var(--surface)); border-color: color-mix(in srgb,var(--t-watch) 28%,var(--border)); }
.kc-callout--gap  { background: color-mix(in srgb,var(--t-sub) 7%,var(--surface));   border-color: color-mix(in srgb,var(--t-sub) 26%,var(--border)); }
.kc-callout-hd   { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.3px; color: var(--ink-2); display: flex; justify-content: space-between; margin-bottom: 7px; }
.kc-callout-hd em { font-style: normal; font-family: 'IBM Plex Mono', monospace; }
.kc-callout--risk .kc-callout-hd em { color: var(--t-watch); }
.kc-callout--gap  .kc-callout-hd em { color: var(--t-sub); }
.kc-callout-row  { font-size: 11px; color: var(--ink-2); line-height: 1.4; padding: 3px 0; border-top: 1px solid var(--border-2); }
.kc-callout-row:first-of-type { border-top: none; }
.kc-callout-empty { font-size: 11px; color: var(--muted); font-style: italic; }
.kc-export-btn   {
    display: flex; align-items: center; justify-content: center; gap: 7px;
    width: 100%; padding: 10px; background: var(--accent); color: #fff;
    border: none; border-radius: 9px; font-size: 13px; font-weight: 600; cursor: pointer;
}
/* legacy compat */
.scheme-block {
    background: color-mix(in srgb, var(--accent) 9%, var(--surface));
    border: 1px solid color-mix(in srgb, var(--accent) 28%, var(--border));
    border-radius: 10px; padding: 1.2rem 1.4rem;
}
.scheme-amount { font-family: 'IBM Plex Mono', monospace; font-size: 2rem; font-weight: 600; color: var(--t-prime); line-height: 1; letter-spacing: -0.03em; }
.flag-item { background: color-mix(in srgb,var(--t-watch) 8%,transparent); border-left: 3px solid var(--t-watch); border-radius: 0 6px 6px 0; padding: 0.42rem 0.75rem; margin-bottom: 0.3rem; font-size: 0.78rem; color: var(--t-watch); }
.gap-item  { background: color-mix(in srgb,var(--t-sub) 8%,transparent);   border-left: 3px solid var(--t-sub);   border-radius: 0 6px 6px 0; padding: 0.42rem 0.75rem; margin-bottom: 0.3rem; font-size: 0.78rem; color: var(--t-sub); }
.alt-row { font-size: 0.78rem; color: var(--muted); padding: 0.3rem 0; border-bottom: 1px solid var(--border-2); }
.underwrite-kv { display: flex; justify-content: space-between; align-items: center; padding: 0.35rem 0; border-bottom: 1px solid var(--border-2); font-size: 0.79rem; }
.underwrite-kv-key { color: var(--muted); }
.underwrite-kv-val { font-weight: 600; color: var(--ink); font-family: 'IBM Plex Mono', monospace; }

/* ─────────────────────────────────────────────────────────────────────────
   SMART ONBOARDING — KarigarCred Field Assistant
───────────────────────────────────────────────────────────────────────── */
.ob-sample-label {
    font-size: 0.6rem; font-weight: 700; letter-spacing: 0.13em;
    text-transform: uppercase; color: var(--muted);
    margin-bottom: 0.5rem; margin-top: 0.2rem;
}
.ob-card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 13px; overflow: hidden;
}
.ob-card-hd {
    display: flex; align-items: center; justify-content: space-between;
    padding: 12px 14px; border-bottom: 1px solid var(--border-2);
}
.ob-card-hd-t {
    font-size: 12px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.4px; color: var(--ink-2);
}
.ob-card-hd-b { font-size: 10.5px; color: var(--t-prime); font-weight: 600; }
.ob-card-title {
    font-size: 0.6rem; font-weight: 700; letter-spacing: 0.12em;
    text-transform: uppercase; color: var(--muted);
    padding: 12px 14px 0; margin-bottom: 0;
}
.ob-param {
    display: flex; align-items: center; gap: 11px;
    padding: 11px 14px; border-bottom: 1px solid var(--border-2);
}
.ob-param:last-child { border-bottom: none; }
.ob-param-row {
    display: flex; justify-content: space-between; align-items: center;
    padding: 0.58rem 0.875rem; border-bottom: 1px solid var(--border-2);
    font-size: 0.84rem;
}
.ob-param-row:last-child { border-bottom: none; }
.ob-param-key  { font-size: 11px; color: var(--muted); }
.ob-param-val  { font-size: 14px; font-weight: 600; color: var(--ink); text-align: right; margin-top: 1px; }
.ob-param-val.detected { color: var(--t-prime); }
.ob-param-val.missing  { color: var(--faint); font-style: italic; font-weight: 400; }
.ob-check-ok { width:22px; height:22px; border-radius:6px; display:grid; place-items:center; flex:none; background:color-mix(in srgb,var(--t-prime) 14%,transparent); color:var(--t-prime); font-size:13px; }
.ob-check-no { width:22px; height:22px; border-radius:6px; display:grid; place-items:center; flex:none; background:var(--surface-3); color:var(--faint); font-size:13px; }
.ob-score-big  { font-family: 'IBM Plex Mono', monospace; font-size: 3rem; font-weight: 600; text-align: center; line-height: 1.1; letter-spacing: -1px; }
.ob-flag-row {
    display: flex; gap: 9px; align-items: flex-start;
    padding: 5px 14px; font-size: 12px; color: var(--ink-2); line-height: 1.4;
    border-top: 1px solid var(--border-2);
}
.ob-flag-row:first-of-type { border-top: none; }
.ob-co-risk { width:16px; height:16px; border-radius:5px; flex:none; display:grid; place-items:center; margin-top:1px; font-size:9px; font-weight:700; color:#fff; background:var(--t-watch); }
.ob-co-gap  { width:16px; height:16px; border-radius:5px; flex:none; display:grid; place-items:center; margin-top:1px; font-size:9px; font-weight:700; color:#fff; background:var(--t-sub); }
.ob-co-ok   { width:16px; height:16px; border-radius:5px; flex:none; display:grid; place-items:center; margin-top:1px; font-size:9px; font-weight:700; color:#fff; background:var(--t-prime); }
.ob-gap-row {
    display: flex; gap: 9px; align-items: flex-start;
    padding: 5px 14px; font-size: 12px; color: var(--ink-2); line-height: 1.4;
    border-top: 1px solid var(--border-2);
}
.ob-processing {
    display: flex; align-items: center; gap: 0.8rem;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 11px; padding: 0.85rem 1.3rem;
    font-size: 0.86rem; color: var(--ink-2); font-weight: 500;
}
.ob-pulse {
    width: 10px; height: 10px; border-radius: 50%;
    background: var(--accent); flex-shrink: 0;
    animation: ob-anim 1s infinite;
}
@keyframes ob-anim {
    0%,100% { opacity: 0.3; transform: scale(0.8); }
    50%      { opacity: 1;   transform: scale(1.1); }
}
.ob-lang-seg {
    display: flex; gap: 4px; background: var(--surface-2);
    border: 1px solid var(--border); border-radius: 11px; padding: 4px;
    margin-bottom: 12px;
}
.ob-lang-btn {
    flex: 1; padding: 9px 4px; font-size: 13px; font-weight: 600;
    border: none; background: none; color: var(--muted); border-radius: 8px;
    cursor: pointer; font-family: 'IBM Plex Sans', 'Noto Sans Devanagari', sans-serif;
    transition: background 0.15s;
}
.ob-lang-btn.on { background: var(--accent); color: #fff; }
.ob-chip-row { display: flex; gap: 7px; flex-wrap: wrap; margin-bottom: 10px; }
.ob-chip {
    font-size: 12px; font-weight: 500; color: var(--ink-2);
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; padding: 7px 11px; cursor: pointer;
}
.ob-chip.on { border-color: var(--accent); color: var(--accent); background: color-mix(in srgb,var(--accent) 8%,var(--surface)); }

/* ─────────────────────────────────────────────────────────────────────────
   EMPTY STATE
───────────────────────────────────────────────────────────────────────── */
.empty-state {
    text-align: center; padding: 3.5rem 1.5rem;
    background: var(--surface); border: 1px dashed var(--border);
    border-radius: 12px; margin: 0.5rem 0;
}
.empty-icon  { font-size: 2.2rem; color: var(--faint); margin-bottom: 0.7rem; }
.empty-title { font-size: 0.95rem; font-weight: 700; color: var(--muted); margin-bottom: 0.4rem; }
.empty-sub   { font-size: 0.8rem; color: var(--faint); max-width: 360px; margin: 0 auto; line-height: 1.55; }

/* ─────────────────────────────────────────────────────────────────────────
   AUTH — LOGIN PAGE
───────────────────────────────────────────────────────────────────────── */
.auth-wrap {
    display: flex; flex-direction: column;
    align-items: center; padding: 3rem 1rem;
}
.auth-logo-row {
    display: flex; align-items: center; gap: 12px;
    margin-bottom: 0.6rem;
}
.auth-logo-mark {
    width: 44px; height: 44px; border-radius: 12px;
    background: var(--accent); display: grid; place-items: center;
    color: #fff; font-size: 22px; box-shadow: var(--shadow-sm);
}
.auth-brand-name {
    font-size: 1.9rem; font-weight: 700; color: var(--ink);
    letter-spacing: -0.04em;
}
.auth-title-row {
    font-size: 1.05rem; font-weight: 600; color: var(--ink-2);
    text-align: center; margin-bottom: 0.25rem;
}
.auth-sub-row {
    font-size: 0.78rem; color: var(--muted); text-align: center; margin-bottom: 2rem;
}

/* ─────────────────────────────────────────────────────────────────────────
   AUTH — SIDEBAR BANNER
───────────────────────────────────────────────────────────────────────── */
.auth-banner {
    background: color-mix(in srgb, var(--accent) 10%, var(--surface));
    border: 1px solid color-mix(in srgb, var(--accent) 22%, var(--border));
    border-radius: 10px; padding: 0.85rem 1rem; margin-bottom: 0.6rem;
}
.auth-banner-name {
    font-size: 0.9rem !important; font-weight: 700 !important;
    color: var(--ink) !important; margin-bottom: 0.2rem;
}
.auth-banner-tier {
    font-size: 0.62rem !important; font-weight: 700 !important;
    letter-spacing: 0.1em; text-transform: uppercase;
    color: var(--accent) !important;
}

/* ─────────────────────────────────────────────────────────────────────────
   PERMISSION ERROR STATE
───────────────────────────────────────────────────────────────────────── */
.perm-error {
    text-align: center; padding: 4rem 2rem;
    background: color-mix(in srgb,var(--t-sub) 4%,var(--surface));
    border: 1px dashed color-mix(in srgb,var(--t-sub) 22%,var(--border)); border-radius: 14px;
    margin: 1.5rem 0;
}
.perm-error-icon  { font-size: 2.4rem; color: var(--t-sub); margin-bottom: 0.8rem; }
.perm-error-title { font-size: 1rem; font-weight: 700; color: var(--t-sub); margin-bottom: 0.45rem; }
.perm-error-sub   { font-size: 0.82rem; color: var(--muted); max-width: 400px; margin: 0 auto; line-height: 1.6; }

/* ─────────────────────────────────────────────────────────────────────────
   AUDIT LOG
───────────────────────────────────────────────────────────────────────── */
.audit-stat {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; padding: 1rem 1.2rem; text-align: center;
}
.audit-stat-val {
    font-family: 'IBM Plex Mono', monospace; font-size: 1.8rem; font-weight: 600;
    color: var(--accent); line-height: 1; letter-spacing: -0.03em;
}
.audit-stat-lbl {
    font-size: 0.6rem; font-weight: 700; letter-spacing: 0.12em;
    text-transform: uppercase; color: var(--muted); margin-top: 0.3rem;
}

/* ─────────────────────────────────────────────────────────────────────────
   WHATSAPP BUSINESS SIMULATION SANDBOX
───────────────────────────────────────────────────────────────────────── */
.wa-phone  { background:#E5DDD5; border-radius:16px; overflow:hidden; border:2px solid #2E323D; max-width:390px; margin:0 auto; box-shadow:0 12px 40px rgba(0,0,0,.55); font-family:-apple-system,'Helvetica Neue',sans-serif; }
.wa-status { background:#054C41; color:rgba(255,255,255,.85); font-size:.58rem; padding:.18rem .9rem; display:flex; justify-content:space-between; letter-spacing:.03em; }
.wa-header { background:#075E54; padding:.55rem .85rem; display:flex; align-items:center; gap:.6rem; }
.wa-avatar { width:34px; height:34px; background:#25D366; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:1rem; font-weight:700; color:#fff; flex-shrink:0; }
.wa-cname  { font-size:.84rem; font-weight:700; color:#fff; line-height:1.1; }
.wa-cstat  { font-size:.58rem; color:#A8D5A2; }
.wa-body   { background:#E5DDD5; padding:.65rem .75rem; min-height:300px; max-height:420px; overflow-y:auto; display:flex; flex-direction:column; gap:.38rem; }
.wa-divider { text-align:center; font-size:.64rem; color:#555; background:rgba(255,255,255,.55); border-radius:6px; padding:.12rem .6rem; align-self:center; margin:.25rem 0; }
.wa-in  { background:#fff; color:#111; border-radius:0 8px 8px 8px; padding:.42rem .65rem; max-width:83%; align-self:flex-start; box-shadow:0 1px 2px rgba(0,0,0,.1); font-size:.78rem; line-height:1.48; }
.wa-out { background:#DCF8C6; color:#111; border-radius:8px 0 8px 8px; padding:.42rem .65rem; max-width:83%; align-self:flex-end; box-shadow:0 1px 2px rgba(0,0,0,.1); font-size:.78rem; line-height:1.48; }
.wa-ts  { font-size:.56rem; color:#888; margin-top:.12rem; }
.wa-ts-r { text-align:right; }
.wa-attach { background:rgba(0,0,0,.06); border-radius:6px; padding:.3rem .45rem; font-size:.72rem; color:#333; display:flex; align-items:center; gap:.35rem; }
.wa-bar { background:#F0F0F0; padding:.42rem .65rem; display:flex; align-items:center; gap:.45rem; border-top:1px solid #ccc; }
.wa-pill { background:#fff; border-radius:18px; padding:.32rem .7rem; font-size:.72rem; color:#aaa; flex:1; border:1px solid #e0e0e0; }
.wa-send { background:#25D366; color:#fff; border-radius:50%; width:32px; height:32px; display:flex; align-items:center; justify-content:center; font-size:.9rem; flex-shrink:0; }
.wa-ocr-panel { background:#13161E; border:1px solid #2E323D; border-radius:12px; padding:1.15rem 1.35rem; }
.wa-ocr-hdr { font-size:.59rem; font-weight:700; letter-spacing:.13em; text-transform:uppercase; color:#475569; margin-bottom:.7rem; padding-bottom:.4rem; border-bottom:1px solid #2E323D; }
.wa-ocr-text { font-family:'SF Mono','Courier New',monospace; font-size:.7rem; color:#94A3B8; background:#0D1117; border:1px solid #2E323D; border-radius:8px; padding:.7rem; line-height:1.65; white-space:pre-wrap; }
.wa-success { background:linear-gradient(135deg,rgba(16,185,129,.15) 0%,rgba(16,185,129,.05) 100%); border:1px solid rgba(16,185,129,.38); border-radius:10px; padding:.8rem 1.1rem; display:flex; align-items:center; gap:.7rem; font-size:.8rem; color:#6EE7B7; font-weight:600; }
.wa-dot { width:9px; height:9px; border-radius:50%; background:#10B981; flex-shrink:0; animation:wa-blink .9s ease-in-out infinite; }
@keyframes wa-blink { 0%,100%{transform:scale(1);opacity:1;} 50%{transform:scale(1.9);opacity:.35;} }
.wa-kv { display:flex; justify-content:space-between; align-items:center; padding:.3rem 0; border-bottom:1px solid #1E2229; font-size:.77rem; }
.wa-kv:last-child { border-bottom:none; }
.wa-kv-k { color:#64748B; }
.wa-kv-v { font-weight:700; color:#F1F5F9; }

/* ─────────────────────────────────────────────────────────────────────────
   ARTISAN DIRECTORY (sidebar)
───────────────────────────────────────────────────────────────────────── */
.kc-dir-row {
    display: flex; align-items: center; gap: 10px;
    padding: 8px 9px; border-radius: 8px; border: 1px solid transparent;
    background: none; cursor: pointer; text-align: left; width: 100%;
    font-family: 'IBM Plex Sans', sans-serif; margin-bottom: 2px;
}
.kc-dir-row:hover { background: var(--surface-2); }
.kc-dir-row.active {
    background: var(--surface-2); border-color: var(--border);
    box-shadow: var(--shadow-sm);
}
.kc-dir-bar { width: 3px; height: 30px; border-radius: 2px; flex: none; }
.kc-dir-name { display: block; font-size: 13px; font-weight: 600; color: var(--ink); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.kc-dir-meta { display: block; font-size: 11px; color: var(--muted); margin-top: 1px; }
.kc-dir-score { font-family: 'IBM Plex Mono', monospace; font-size: 14px; font-weight: 600; }

/* ── Hide Streamlit chrome ───────────────────────────────────────── */
#MainMenu { visibility: hidden; }
footer     { visibility: hidden; }
header     { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# Authentication config
# ──────────────────────────────────────────────────────────────────────────────

def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


USERS: dict[str, dict] = {
    "manager": {
        "password_hash": _hash("password123"),
        "display_name":  "Credit Manager",
        "role":          "Bank Underwriter",
        "role_tier":     "Institutional Underwriter",
        "is_manager":    True,
    },
    "assistant": {
        "password_hash": _hash("password123"),
        "display_name":  "Field Assistant",
        "role":          "Artisan Assistant / NGO Facilitator",
        "role_tier":     "NGO Facilitator",
        "is_manager":    False,
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# Audit logging
# ──────────────────────────────────────────────────────────────────────────────

def _init_audit_table() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp      TEXT    NOT NULL,
            username       TEXT    NOT NULL,
            action         TEXT    NOT NULL,
            artisan_target TEXT,
            result_status  TEXT
        )
    """)
    conn.commit()
    conn.close()


def _log_action(username: str, action: str, artisan_target: str, result_status: str) -> None:
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO audit_logs (timestamp, username, action, artisan_target, result_status) "
            "VALUES (?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(timespec="seconds"),
             username, action, artisan_target, result_status),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def _load_audit_logs() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df   = pd.read_sql(
        "SELECT timestamp, username, action, artisan_target, result_status "
        "FROM audit_logs ORDER BY id DESC",
        conn,
    )
    conn.close()
    return df


# ──────────────────────────────────────────────────────────────────────────────
# Login page
# ──────────────────────────────────────────────────────────────────────────────

def _render_login() -> None:
    _, center, _ = st.columns([1, 1.1, 1])
    with center:
        st.markdown("""
        <div class='auth-wrap'>
            <div class='auth-logo-row'>
                <div class='auth-logo-mark'>◈</div>
                <div class='auth-brand-name'>KarigarCred</div>
            </div>
            <div class='auth-title-row'>Institutional Underwriting Terminal</div>
            <div class='auth-sub-row'>Lucknow Textile Cluster &nbsp;·&nbsp; Alternative Credit Scoring System</div>
        </div>
        """, unsafe_allow_html=True)

        if st.session_state.get("_login_error"):
            st.error("Invalid credentials — please check your username and password.")

        with st.form("login_form", clear_on_submit=False):
            username  = st.text_input("Username", placeholder="e.g. manager")
            password  = st.text_input("Password", type="password", placeholder="Enter your password")
            submitted = st.form_submit_button(
                "Sign In  →", use_container_width=True, type="primary",
            )

        if submitted:
            user = USERS.get(username)
            if user and user["password_hash"] == _hash(password):
                st.session_state["auth_authenticated"] = True
                st.session_state["auth_username"]      = username
                st.session_state["auth_display_name"]  = user["display_name"]
                st.session_state["auth_role"]          = user["role"]
                st.session_state["auth_role_tier"]     = user["role_tier"]
                st.session_state["auth_is_manager"]    = user["is_manager"]
                st.session_state.pop("_login_error", None)
                st.rerun()
            else:
                st.session_state["_login_error"] = True
                st.rerun()

        st.markdown(
            "<div style='text-align:center;margin-top:1.2rem;"
            "font-size:0.72rem;color:#374151'>"
            "Demo credentials — Bank Underwriter: <code>manager</code> &nbsp;|&nbsp; "
            "NGO Facilitator: <code>assistant</code> &nbsp;(password: <code>password123</code>)"
            "</div>",
            unsafe_allow_html=True,
        )


# ──────────────────────────────────────────────────────────────────────────────
# Multilingual UI strings
# ──────────────────────────────────────────────────────────────────────────────

TRANSLATIONS: dict[str, dict] = {
    "English": {
        "dashboard_tab":     "📊 Credit Dashboard",
        "onboarding_tab":    "🗣️ Smart Onboarding",
        "page_header":       "Conversational Artisan Onboarding",
        "page_sub":          "Paste or type the artisan's trade statement — English, Hindi, or Awadhi.",
        "sample_label":      "Load a sample statement:",
        "btn_en":            "English",
        "btn_hi":            "Hindi (हिन्दी)",
        "btn_aw":            "Awadhi (अवधी)",
        "input_label":       "Artisan Trade Statement",
        "input_placeholder": "Describe the embroidery workshop, monthly sales, payment cycles, and loan needs…",
        "analyze_btn":       "Analyze Statement →",
        "processing":        "Parsing multilingual statement…",
        "no_input_warn":     "Please enter or load a trade statement first.",
        "extracted_title":   "Extracted Trade Parameters",
        "rec_title":         "Localized Agent Recommendation",
        "cluster_label":     "Cluster Identified",
        "turnover_label":    "Detected Monthly Volume",
        "latency_label":     "Payment Latency",
        "loan_req_label":    "Requested Loan",
        "not_detected":      "Not detected",
        "days_suffix":       "days",
        "score_label":       "Alternative Credit Score",
        "band_label":        "Credit Band",
        "scheme_label":      "Recommended Scheme",
        "max_loan_label":    "Max Eligible Loan",
        "confidence_label":  "Match Confidence",
        "alt_label":         "Alternative Schemes",
        "risk_label":        "Risk Signals",
        "gaps_label":        "Eligibility Gaps",
        "none_label":        "No issues identified",
        "await_title":       "Awaiting Artisan Ingest",
        "await_sub":         "Load a sample template or type a trade statement above to begin multilingual extraction.",
        "push":              "Push to underwriter",
        "pushed":            "Sent to underwriting queue",
        "bands": {
            "Prime":            "Prime",
            "Near-Prime":       "Near-Prime",
            "Subprime":         "Subprime",
            "Deep Subprime":    "Deep Subprime",
            "Credit Invisible": "Credit Invisible",
        },
        "schemes": {
            "MUDRA Shishu":     "MUDRA Shishu",
            "MUDRA Kishor":     "MUDRA Kishor",
            "MUDRA Tarun":      "MUDRA Tarun",
            "PM Vishwakarma":   "PM Vishwakarma",
            "ODOP Credit Line": "ODOP Credit Line",
        },
    },
    "Hindi (हिन्दी)": {
        "dashboard_tab":     "📊 क्रेडिट डैशबोर्ड",
        "onboarding_tab":    "🗣️ स्मार्ट ऑनबोर्डिंग",
        "page_header":       "बातचीत आधारित कारीगर ऑनबोर्डिंग",
        "page_sub":          "कारीगर का व्यापार विवरण दर्ज करें — हिंदी, अंग्रेज़ी या अवधी में।",
        "sample_label":      "नमूना विवरण लोड करें:",
        "btn_en":            "अंग्रेज़ी",
        "btn_hi":            "हिंदी",
        "btn_aw":            "अवधी",
        "input_label":       "कारीगर का व्यापार विवरण",
        "input_placeholder": "कारखाने, मासिक बिक्री, भुगतान चक्र और ऋण की ज़रूरत बताएं…",
        "analyze_btn":       "विश्लेषण करें →",
        "processing":        "बहुभाषी विवरण विश्लेषण हो रहा है…",
        "no_input_warn":     "कृपया पहले कोई व्यापार विवरण दर्ज करें।",
        "extracted_title":   "निकाले गए व्यापार मापदंड",
        "rec_title":         "स्थानीय एजेंट की सिफ़ारिश",
        "cluster_label":     "क्षेत्र पहचाना",
        "turnover_label":    "मासिक कारोबार",
        "latency_label":     "भुगतान में देरी",
        "loan_req_label":    "अनुरोधित ऋण",
        "not_detected":      "पता नहीं चला",
        "days_suffix":       "दिन",
        "score_label":       "वैकल्पिक क्रेडिट स्कोर",
        "band_label":        "क्रेडिट श्रेणी",
        "scheme_label":      "अनुशंसित योजना",
        "max_loan_label":    "अधिकतम पात्र ऋण",
        "confidence_label":  "मिलान विश्वास",
        "alt_label":         "वैकल्पिक योजनाएं",
        "risk_label":        "जोखिम संकेत",
        "gaps_label":        "पात्रता अंतराल",
        "none_label":        "कोई समस्या नहीं",
        "await_title":       "प्रतीक्षा में",
        "await_sub":         "ऊपर नमूना लोड करें या विवरण दर्ज करें।",
        "push":              "अंडरराइटर को भेजें",
        "pushed":            "अंडरराइटिंग कतार में भेजा",
        "bands": {
            "Prime":            "उत्तम",
            "Near-Prime":       "लगभग उत्तम",
            "Subprime":         "मध्यम",
            "Deep Subprime":    "कमज़ोर",
            "Credit Invisible": "अदृश्य ऋण",
        },
        "schemes": {
            "MUDRA Shishu":     "मुद्रा शिशु",
            "MUDRA Kishor":     "मुद्रा किशोर",
            "MUDRA Tarun":      "मुद्रा तरुण",
            "PM Vishwakarma":   "पीएम विश्वकर्मा",
            "ODOP Credit Line": "ओडीओपी ऋण लाइन",
        },
    },
    "Awadhi (अवधी)": {
        "dashboard_tab":     "📊 क्रेडिट झाँकी",
        "onboarding_tab":    "🗣️ नाव दर्ज करव",
        "page_header":       "बात-चीत से कारीगर दर्ज करव",
        "page_sub":          "कारीगर का बेपार बिबरन लिखव — हिंदी, अंगरेजी या अवधी मा।",
        "sample_label":      "नमूना बिबरन लोड करव:",
        "btn_en":            "अंगरेजी",
        "btn_hi":            "हिंदी",
        "btn_aw":            "अवधी",
        "input_label":       "कारीगर का बेपार बिबरन",
        "input_placeholder": "आपन कारखाना, महीना कमाई, पइसा आव का बात अउर उधार की जरूरत बताव…",
        "analyze_btn":       "जाँच करव →",
        "processing":        "बिबरन जाँचा जात है…",
        "no_input_warn":     "पहिले कउनो बेपार बिबरन लिखव।",
        "extracted_title":   "निकारे गए बेपार मापदंड",
        "rec_title":         "स्थानीय एजेंट का सुझाव",
        "cluster_label":     "जगह पहचान",
        "turnover_label":    "महीना कमाई",
        "latency_label":     "पइसा मिलब मा देरी",
        "loan_req_label":    "माँगा गया उधार",
        "not_detected":      "नाहीं मिला",
        "days_suffix":       "दिन",
        "score_label":       "वैकल्पिक क्रेडिट स्कोर",
        "band_label":        "क्रेडिट दर्जा",
        "scheme_label":      "सुझाव दिहा योजना",
        "max_loan_label":    "सबसे बड़ा पात्र उधार",
        "confidence_label":  "मिलान विश्वास",
        "alt_label":         "और योजना",
        "risk_label":        "जोखिम संकेत",
        "gaps_label":        "पात्रता कम",
        "none_label":        "कउनो दिक्कत नाहीं",
        "await_title":       "प्रतीक्षा मा",
        "await_sub":         "ऊपर नमूना लोड करव या बिबरन लिखव।",
        "push":              "अंडरराइटर के भेजीं",
        "pushed":            "अंडरराइटिंग कतार मा भेजल",
        "bands": {
            "Prime":            "उत्तम",
            "Near-Prime":       "लगभग उत्तम",
            "Subprime":         "मध्यम",
            "Deep Subprime":    "कमज़ोर",
            "Credit Invisible": "अदृश्य ऋण",
        },
        "schemes": {
            "MUDRA Shishu":     "मुद्रा शिशु",
            "MUDRA Kishor":     "मुद्रा किशोर",
            "MUDRA Tarun":      "मुद्रा तरुण",
            "PM Vishwakarma":   "पीएम विश्वकर्मा",
            "ODOP Credit Line": "ओडीओपी ऋण लाइन",
        },
    },
}

SAMPLES: dict[str, str] = {
    "English": (
        "I run an embroidery workshop in Chowk. My monthly sales on invoices are "
        "around 45,000 rupees but exporters clear bills after 60 days. "
        "I need a loan of 80,000 to buy bulk threads."
    ),
    "Hindi (हिन्दी)": (
        "चौक में चिकनकारी का काम है। महीने का 35,000 रुपये का इनवॉइस बनता है "
        "पर पेमेंट दो महीने बाद मिलती है। क्या सिल्क के कपड़े के लिए "
        "1 लाख का लोन मिल जाएगा?"
    ),
    "Awadhi (अवधी)": (
        "भइया, हम अमिनाबाद मा जरदोजी कै काम करीथिन। महीनवा मा करीब 40,000 "
        "रुपिया आवत है पै महाजन लोग दुई महीना बाद पइसा देवत हैं। "
        "हमका नया फ्रेम खरीदे बदे 50,000 रुपिया चाही।"
    ),
}

# Sample OCR documents for the WhatsApp Simulation Sandbox
_WA_SAMPLES: dict[str, dict] = {
    "📄 Handwritten Khata Bill.jpg  ·  Chowk Cluster": {
        "thumb":         "Khata_Bill_Chowk_Apr2024.jpg",
        "ocr_raw": (
            "कच्चा खाता — चौक, लखनऊ\n"
            "दिनाँक : 15/04/2024\n"
            "ग्राहक : Lucknow Chikankari House\n"
            "माल    : 12 नग कढ़ाई कुर्ता कपड़ा\n"
            "रकम    : ₹18,500\n"
            "GST (5%): ₹925\n"
            "कुल बिल: ₹19,425\n"
            "भुगतान : 45 दिन बाद\n"
            "दस्तखत : रज़िया बेगम ✎"
        ),
        "statement":     (
            "चौक में चिकनकारी का काम है। "
            "महीने का 18,500 रुपये का इनवॉइस बनता है "
            "पर पेमेंट 45 दिन बाद मिलती है।"
        ),
        "invoice_value": 18_500.0,
        "buyer":         "Lucknow Chikankari House",
        "overdue_days":  45,
        "cluster_hint":  "Chowk",
    },
    "📄 Logistics Dispatch Note.png  ·  Aminabad Cluster": {
        "thumb":         "Dispatch_Note_Aminabad_May2024.png",
        "ocr_raw": (
            "DISPATCH NOTE  #DN-2024-0892\n"
            "Supplier : Aminabad Zardozi Workshop\n"
            "Buyer    : Craftroot Exports\n"
            "Date     : 22/05/2024\n"
            "Goods    : Zardozi embroidered sarees — 6 pcs\n"
            "Value    : ₹42,000\n"
            "GST 5%   : ₹2,100\n"
            "Total    : ₹44,100\n"
            "Terms    : Net 60 days from delivery\n"
            "Status   : Dispatched & Confirmed"
        ),
        "statement":     (
            "Aminabad में जरदोजी का काम है। "
            "Monthly invoice around 42,000 rupees. "
            "Bills clear after 60 days. Need a loan of 80,000."
        ),
        "invoice_value": 42_000.0,
        "buyer":         "Craftroot Exports",
        "overdue_days":  60,
        "cluster_hint":  "Aminabad",
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# Core helpers
# ──────────────────────────────────────────────────────────────────────────────

def fmt_inr(v: float) -> str:
    if v >= 1_00_00_000: return f"₹{v/1_00_00_000:.2f} Cr"
    if v >= 1_00_000:    return f"₹{v/1_00_000:.2f} L"
    if v >= 1_000:       return f"₹{v/1_000:.1f} K"
    return f"₹{v:.0f}"


def score_meta(s: int) -> tuple[str, str, str]:
    """Returns (label, badge-css-class, hex-color) for 5-tier KarigarCred bands."""
    if _kc_dark:
        if s >= 760: return "Prime",     "risk-prime",  "#33b07e"
        if s >= 720: return "Strong",    "risk-strong", "#82c64f"
        if s >= 660: return "Standard",  "risk-std",    "#e3b745"
        if s >= 580: return "Watch",     "risk-watch",  "#f0993f"
        return               "Sub-prime","risk-sub",    "#ef6d6d"
    else:
        if s >= 760: return "Prime",     "risk-prime",  "#157f55"
        if s >= 720: return "Strong",    "risk-strong", "#5d9b2f"
        if s >= 660: return "Standard",  "risk-std",    "#c2901f"
        if s >= 580: return "Watch",     "risk-watch",  "#d9772a"
        return               "Sub-prime","risk-sub",    "#c93f3f"


def score_tier(s: int) -> str:
    """Returns T1–T5 tier string for band badge."""
    if s >= 760: return "T1"
    if s >= 720: return "T2"
    if s >= 660: return "T3"
    if s >= 580: return "T4"
    return "T5"


def sig_grade(v: float) -> str:
    """A/B/C/D/E letter grade for signal scores /100."""
    if v >= 82: return "A"
    if v >= 70: return "B"
    if v >= 58: return "C"
    if v >= 46: return "D"
    return "E"


def _build_synthetic_profile(parsed: ParsedStatement) -> CreditProfile:
    """Estimate a CreditProfile from a parsed trade statement."""
    monthly = parsed.monthly_turnover  or 30_000.0
    annual  = monthly * 12
    latency = parsed.payment_latency_days or 45

    if latency <= 30:
        fast_rate, default_rate, cv = 0.90, 0.01, 0.20
    elif latency <= 45:
        fast_rate, default_rate, cv = 0.78, 0.02, 0.28
    elif latency <= 60:
        fast_rate, default_rate, cv = 0.60, 0.05, 0.38
    elif latency <= 90:
        fast_rate, default_rate, cv = 0.42, 0.10, 0.55
    else:
        fast_rate, default_rate, cv = 0.28, 0.20, 0.75

    s_cf  = float(np.clip(100.0 * np.exp(-1.5 * cv), 0.0, 100.0))
    s_ff  = float(np.clip(100.0 * (fast_rate - 2.0 * default_rate), 0.0, 100.0))
    years, repeat = 5, 0.65
    s_rel = float(np.clip(70.0 * repeat + min(30.0, years * 2.0), 0.0, 100.0))

    composite    = 0.30 * s_cf + 0.40 * s_ff + 0.30 * s_rel
    credit_score = int(round(300.0 + (composite / 100.0) * 550.0))

    flags: list[str] = []
    if latency > 60:
        flags.append(f"Payment latency of {latency} days detected — above 60-day threshold")
    if monthly < 20_000:
        flags.append("Low stated monthly turnover may limit MUDRA eligibility")

    return CreditProfile(
        artisan_id           = 0,
        name                 = "Onboarded Artisan",
        cluster              = parsed.cluster or "Unspecified",
        craft_type           = "Textile Artisan",
        artisan_card_status  = "Pending",
        years_active         = years,
        annual_turnover      = float(annual),
        credit_score         = credit_score,
        composite_raw        = round(composite, 2),
        cashflow_score       = round(s_cf, 2),
        fulfillment_score    = round(s_ff, 2),
        relationship_score   = round(s_rel, 2),
        avg_monthly_revenue  = float(monthly),
        revenue_cv_adjusted  = round(cv, 4),
        fast_payment_rate    = round(fast_rate, 4),
        severe_default_rate  = round(default_rate, 4),
        repeat_buyer_rate    = round(repeat, 4),
        total_invoices       = 24,
        unique_buyers        = 6,
        risk_flags           = flags,
    )


def _t_flag(flag: str, lang: str) -> str:
    if lang == "English":
        return flag
    m = re.match(r"Payment latency of (\d+) days detected — above 60-day threshold", flag)
    if m:
        n = m.group(1)
        if lang == "Hindi (हिन्दी)":
            return f"भुगतान में {n} दिन की देरी — 60-दिन सीमा से अधिक"
        return f"{n} दिन पइसा आव मा देरी — 60-दिन सीमा से ऊपर"
    if "Low stated monthly turnover" in flag:
        if lang == "Hindi (हिन्दी)":
            return "कम मासिक कारोबार MUDRA पात्रता को सीमित कर सकता है"
        return "कम महीना कमाई MUDRA पात्रता सीमित कर सकत है"
    return flag


def _t_gap(gap: str, lang: str) -> str:
    if lang == "English":
        return gap
    m = re.match(r"Credit score (\d+) below .+ minimum of (\d+)", gap)
    if m:
        if lang == "Hindi (हिन्दी)":
            return f"क्रेडिट स्कोर {m.group(1)} — न्यूनतम {m.group(2)} से कम"
        return f"क्रेडिट स्कोर {m.group(1)} — कम से कम {m.group(2)} चाही"
    if "Annual turnover" in gap and "below" in gap:
        if lang == "Hindi (हिन्दी)": return "वार्षिक कारोबार न्यूनतम सीमा से कम"
        return "सालाना कमाई न्यूनतम सीमा से कम"
    if "Annual turnover" in gap and "exceeds" in gap:
        if lang == "Hindi (हिन्दी)": return "वार्षिक कारोबार इस योजना की अधिकतम सीमा से अधिक"
        return "सालाना कमाई योजना की ऊपरी सीमा से बाहर"
    if "artisan card" in gap.lower():
        if lang == "Hindi (हिन्दी)": return "इस योजना के लिए सक्रिय आर्टिसन कार्ड आवश्यक है"
        return "इ योजना खातिर आर्टिसन कार्ड चाही"
    if "Years active" in gap:
        if lang == "Hindi (हिन्दी)": return "व्यापार की अवधि न्यूनतम वर्षों की आवश्यकता पूरी नहीं करती"
        return "काम की अवधि न्यूनतम साल से कम बाय"
    return gap


# ──────────────────────────────────────────────────────────────────────────────
# Cached data loaders
# ──────────────────────────────────────────────────────────────────────────────

@st.cache_data
def load_artisan_list() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df   = pd.read_sql(
        "SELECT id, name, cluster, craft_type, annual_turnover, artisan_card_status "
        "FROM artisans ORDER BY name", conn,
    )
    conn.close()
    return df


@st.cache_data
def load_profile(artisan_id: int) -> CreditProfile:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    p    = score_artisan(artisan_id, conn)
    conn.close()
    return p


@st.cache_data
def load_routing(artisan_id: int) -> dict:
    return route_artisan(load_profile(artisan_id), DB_PATH)


@st.cache_data
def load_invoices(artisan_id: int) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df   = pd.read_sql(
        "SELECT invoice_date, buyer_name, invoice_value, tax_paid, "
        "payment_status, overdue_days FROM gst_invoices "
        "WHERE artisan_id=? ORDER BY invoice_date DESC",
        conn, params=(artisan_id,),
    )
    conn.close()
    df["invoice_date"] = pd.to_datetime(df["invoice_date"])
    return df


@st.cache_data
def load_ledger(artisan_id: int) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df   = pd.read_sql(
        "SELECT buyer_name, order_date, delivery_date, settlement_date, "
        "order_value, settlement_time_days, is_repeat_buyer "
        "FROM order_ledgers WHERE artisan_id=? ORDER BY order_date DESC",
        conn, params=(artisan_id,),
    )
    conn.close()
    return df


def _wa_insert_invoice(artisan_id: int, buyer: str, value: float, overdue_days: int) -> str:
    """Insert a WhatsApp-streamed invoice into the live DB and bust per-artisan caches."""
    import uuid as _uuid
    from datetime import date as _date

    inv_num  = f"WA-{artisan_id:03d}-{_uuid.uuid4().hex[:8].upper()}"
    inv_date = _date.today().isoformat()
    tax      = round(value * 0.05, 2)
    status   = "Paid" if overdue_days == 0 else ("Pending" if overdue_days <= 60 else "Overdue")

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO gst_invoices "
        "(artisan_id, invoice_number, invoice_date, buyer_name, "
        " invoice_value, tax_paid, payment_status, overdue_days) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (artisan_id, inv_num, inv_date, buyer, value, tax, status, overdue_days),
    )
    conn.commit()
    conn.close()

    load_profile.clear()
    load_invoices.clear()
    load_routing.clear()

    return inv_num


# ──────────────────────────────────────────────────────────────────────────────
# Dark-mode Plotly charts
# ──────────────────────────────────────────────────────────────────────────────

_CHART_BG    = "rgba(0,0,0,0)"
_CHART_FONT  = "#b8bec9" if _kc_dark else "#3c424d"
_CHART_GRID  = "#222730" if _kc_dark else "#ecebe5"
_CHART_TICK  = "#5c636f" if _kc_dark else "#878d99"
_ACCENT_HEX  = "#4f46d6"
_DARK_LAYOUT = dict(
    paper_bgcolor=_CHART_BG,
    plot_bgcolor=_CHART_BG,
    font=dict(family="IBM Plex Sans,system-ui,sans-serif", color=_CHART_FONT),
)
_AXIS_STYLE = dict(
    showgrid=True, gridcolor=_CHART_GRID,
    tickfont=dict(size=9, color=_CHART_TICK, family="IBM Plex Mono,monospace"),
    linecolor=_CHART_GRID, tickcolor=_CHART_GRID,
)


def chart_gauge(score: int, color: str) -> go.Figure:
    sub_alpha = "22"
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number={"font": {"size": 48, "color": color, "family": "IBM Plex Mono,monospace"}},
        gauge={
            "axis": {
                "range": [300, 850],
                "tickvals": [300, 580, 660, 720, 760, 850],
                "tickfont": {"size": 8, "color": _CHART_TICK, "family": "IBM Plex Mono,monospace"},
                "tickcolor": _CHART_GRID,
            },
            "bar":       {"color": color, "thickness": 0.22},
            "bgcolor":   "rgba(0,0,0,0)",
            "borderwidth": 0,
            "steps": [
                {"range": [300, 580], "color": f"rgba(239,109,109,0.10)"},
                {"range": [580, 660], "color": f"rgba(240,153,63,0.10)"},
                {"range": [660, 720], "color": f"rgba(227,183,69,0.10)"},
                {"range": [720, 760], "color": f"rgba(130,198,79,0.10)"},
                {"range": [760, 850], "color": f"rgba(51,176,126,0.10)"},
            ],
        },
    ))
    fig.update_layout(
        height=220, margin=dict(t=15, b=0, l=20, r=20),
        **_DARK_LAYOUT,
    )
    return fig


def chart_subscores(profile: CreditProfile) -> go.Figure:
    cats   = ["Relationship (30%)", "Fulfillment (40%)", "Cash Flow (30%)"]
    vals   = [profile.relationship_score, profile.fulfillment_score, profile.cashflow_score]
    band_col = score_meta(profile.credit_score)[2]
    colors   = [band_col, band_col, band_col]

    fig = go.Figure(go.Bar(
        y=cats, x=vals, orientation="h",
        marker_color=colors,
        text=[f"{v:.0f}" for v in vals],
        textposition="inside", insidetextanchor="middle",
        textfont={"size": 11, "color": "white", "family": "IBM Plex Mono,monospace"},
        hovertemplate="%{y}: %{x:.1f}/100<extra></extra>",
    ))
    fig.add_vline(
        x=profile.composite_raw, line_dash="dot",
        line_color=_CHART_FONT, line_width=1.5,
        annotation_text=f"  {profile.composite_raw:.0f}",
        annotation_position="top right",
        annotation_font_size=9, annotation_font_color=_CHART_FONT,
    )
    fig.update_layout(
        xaxis=dict(range=[0, 100], title="", **_AXIS_STYLE),
        yaxis=dict(showgrid=False, tickfont={"size": 9, "color": _CHART_FONT}),
        showlegend=False,
        height=190,
        margin=dict(t=10, b=25, l=10, r=55),
        **_DARK_LAYOUT,
    )
    return fig


def chart_revenue(invoices: pd.DataFrame) -> go.Figure:
    df = invoices.copy()
    df["year_month"]    = df["invoice_date"].dt.to_period("M").astype(str)
    df["month_num"]     = df["invoice_date"].dt.month
    df["season_factor"] = df["month_num"].map(MONTHLY_SEASONALITY)
    df["adj_value"]     = df["invoice_value"] / df["season_factor"]

    m_actual = df.groupby("year_month")["invoice_value"].sum().reset_index()
    m_adj    = df.groupby("year_month")["adj_value"].sum().reset_index()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=m_actual["year_month"], y=m_actual["invoice_value"],
        mode="lines+markers", name="Actual Revenue",
        line=dict(color=_ACCENT_HEX, width=2.5), marker=dict(size=4),
        fill="tozeroy", fillcolor=f"rgba(79,70,214,0.08)",
        hovertemplate="%{x}: ₹%{y:,.0f}<extra>Actual</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=m_adj["year_month"], y=m_adj["adj_value"],
        mode="lines", name="Seasonality-Adjusted",
        line=dict(color=_CHART_TICK, width=1.5, dash="dot"),
        hovertemplate="%{x}: ₹%{y:,.0f}<extra>Adjusted</extra>",
    ))
    fig.update_layout(
        xaxis=dict(showgrid=False, tickangle=-45,
                   tickfont=dict(size=8, color="#64748B"), nticks=12,
                   linecolor="#2E323D"),
        yaxis=dict(title="Revenue (₹)", **_AXIS_STYLE,
                   tickformat=",.0f"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1, font=dict(size=9, color="#64748B"),
                    bgcolor="rgba(0,0,0,0)"),
        height=285, margin=dict(t=30, b=60, l=70, r=15),
        **_DARK_LAYOUT,
    )
    return fig


def chart_latency(invoices: pd.DataFrame) -> go.Figure:
    total  = len(invoices)
    od     = invoices["overdue_days"]
    labels = ["0–30d\nPrompt", "31–60d\nStandard", "61–90d\nLate",
              "91–120d\nOverdue", "120+d\nDefault"]
    counts = [
        int((od <= 30).sum()),
        int(((od > 30) & (od <= 60)).sum()),
        int(((od > 60) & (od <= 90)).sum()),
        int(((od > 90) & (od <= 120)).sum()),
        int((od > 120).sum()),
    ]
    pcts   = [f"{c / total:.0%}" for c in counts]
    if _kc_dark:
        colors = ["#33b07e", "#82c64f", "#e3b745", "#f0993f", "#ef6d6d"]
    else:
        colors = ["#157f55", "#5d9b2f", "#c2901f", "#d9772a", "#c93f3f"]

    fig = go.Figure(go.Bar(
        x=labels, y=counts, marker_color=colors,
        text=pcts, textposition="outside",
        textfont=dict(size=10, color="#94A3B8"),
        hovertemplate="%{x}<br>Count: %{y} (%{text})<extra></extra>",
        marker_line_width=0,
    ))
    fig.update_layout(
        xaxis=dict(showgrid=False, tickfont=dict(size=9, color="#94A3B8"),
                   linecolor="#2E323D"),
        yaxis=dict(title="Invoice Count", **_AXIS_STYLE),
        height=275, margin=dict(t=30, b=20, l=55, r=20),
        showlegend=False,
        **_DARK_LAYOUT,
    )
    return fig


# ──────────────────────────────────────────────────────────────────────────────
# Guard: database must exist
# ──────────────────────────────────────────────────────────────────────────────

if not os.path.exists(DB_PATH):
    st.error(
        "**Database not found.** "
        "Run `python3 main.py` in this directory to initialise and populate it, "
        "then refresh this page."
    )
    st.stop()


# ──────────────────────────────────────────────────────────────────────────────
# Auth guard — show login page if not authenticated
# ──────────────────────────────────────────────────────────────────────────────

if not st.session_state.get("auth_authenticated"):
    _render_login()
    st.stop()

# Session is authenticated — pull identity from state
_init_audit_table()
_username     = st.session_state["auth_username"]
_display_name = st.session_state["auth_display_name"]
_role_tier    = st.session_state["auth_role_tier"]
_is_manager   = st.session_state["auth_is_manager"]


# ──────────────────────────────────────────────────────────────────────────────
# Sidebar — auth banner + language + artisan selector (manager only)
# ──────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    # ── KarigarCred brand + account banner ──────────────────────────────────
    st.markdown(
        f"""<div style='display:flex;align-items:center;gap:10px;padding:6px 2px 10px'>
            <div style='width:32px;height:32px;border-radius:9px;background:var(--accent);
                        display:grid;place-items:center;color:#fff;font-size:16px;flex:none'>◈</div>
            <div>
              <div style='font-weight:700;font-size:15px;color:var(--ink)'>KarigarCred</div>
              <div style='font-size:10px;color:var(--muted);letter-spacing:.3px;text-transform:uppercase'>Field Terminal</div>
            </div>
        </div>
        <div class='auth-banner'>
            <div class='auth-banner-name'>{_display_name}</div>
            <div class='auth-banner-tier'>{_role_tier}</div>
        </div>""",
        unsafe_allow_html=True,
    )

    _sb_col1, _sb_col2 = st.columns([3, 1])
    with _sb_col1:
        if st.button("Log Out", key="logout_btn", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    with _sb_col2:
        _dm_icon = "☀" if _kc_dark else "☾"
        if st.button(_dm_icon, key="dark_mode_btn", use_container_width=True,
                     help="Toggle light/dark mode"):
            st.session_state["kc_dark"] = not _kc_dark
            st.rerun()

    st.divider()

    lang = st.radio(
        "Language / भाषा",
        ["English", "Hindi (हिन्दी)", "Awadhi (अवधी)"],
        horizontal=True,
        key="interface_lang",
    )
    tr = TRANSLATIONS[lang]

    if _is_manager:
        st.divider()
        st.markdown(
            "<div style='font-size:12px;font-weight:600;text-transform:uppercase;"
            "letter-spacing:.6px;color:var(--muted);padding:2px 0 8px'>Artisan Directory</div>",
            unsafe_allow_html=True,
        )
        all_artisans = load_artisan_list()

        search      = st.text_input("", placeholder="Name, craft, or ID…",
                                    label_visibility="collapsed")
        cluster_opt = st.radio("Cluster", ["All", "Chowk", "Aminabad"], horizontal=True)

        view = all_artisans.copy()
        if search:
            view = view[view["name"].str.contains(search, case=False, na=False)]
        if cluster_opt != "All":
            view = view[view["cluster"] == cluster_opt]

        if view.empty:
            st.warning("No artisans match this filter.")
            st.stop()

        view        = view.copy()
        view["label"] = view.apply(
            lambda r: f"{r['name']}  ·  {r['cluster']}  ·  {r['craft_type']}", axis=1
        )
        chosen_label = st.selectbox("", options=view["label"].tolist(),
                                    label_visibility="collapsed")
        chosen_row   = view[view["label"] == chosen_label].iloc[0]
        artisan_id   = int(chosen_row["id"])

        st.divider()
        _art_score_preview = load_profile(artisan_id).credit_score
        _art_band_lbl, _, _art_band_col = score_meta(_art_score_preview)
        st.markdown(
            f"<div style='font-weight:700;font-size:14px;color:var(--ink)'>{chosen_row['name']}</div>"
            f"<div style='font-size:11px;color:var(--muted);margin-top:2px'>"
            f"ART-{artisan_id:04d} · {chosen_row['cluster']} · {chosen_row['craft_type'].split()[0]}</div>"
            f"<div style='margin-top:8px;display:flex;align-items:center;gap:8px'>"
            f"<span style='font-family:IBM Plex Mono,monospace;font-size:20px;font-weight:600;"
            f"color:{_art_band_col}'>{_art_score_preview}</span>"
            f"<span class='risk-badge risk-{_art_band_lbl.lower().replace(' ', '-')}'>"
            f"{_art_band_lbl}</span></div>",
            unsafe_allow_html=True,
        )
        st.metric("Annual Turnover", fmt_inr(float(chosen_row["annual_turnover"])))
        st.metric("Card Status",     chosen_row["artisan_card_status"])


# ──────────────────────────────────────────────────────────────────────────────
# Main tab bar — role-aware
# ──────────────────────────────────────────────────────────────────────────────

if _is_manager:
    tab_dash, tab_onboard, tab_wa, tab_audit = st.tabs([
        tr["dashboard_tab"],
        tr["onboarding_tab"],
        "💬 WhatsApp Sandbox",
        "🔒 Audit Logs",
    ])
else:
    _tab_list   = st.tabs([tr["onboarding_tab"], "💬 WhatsApp Sandbox"])
    tab_onboard = _tab_list[0]
    tab_wa      = _tab_list[1]


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 1 — CREDIT DASHBOARD  (Bank Underwriter only)
# ══════════════════════════════════════════════════════════════════════════════

if _is_manager:
    with tab_dash:
        profile   = load_profile(artisan_id)
        routing   = load_routing(artisan_id)
        invoices  = load_invoices(artisan_id)
        ledger    = load_ledger(artisan_id)

        # Audit: log once per artisan viewed per session
        _last_logged = st.session_state.get("_audit_last_artisan")
        if _last_logged != artisan_id:
            _log_action(
                _username, "CREDIT_SCORE_VIEWED",
                profile.name, f"Score:{profile.credit_score}",
            )
            st.session_state["_audit_last_artisan"] = artisan_id

        band_label, band_css, band_color = score_meta(profile.credit_score)
        band_tier = score_tier(profile.credit_score)

        rec_scheme = routing.get("recommended_scheme")
        loan_amt   = float(routing.get("max_eligible_loan_amount", 0.0))
        confidence = float(routing.get("confidence_score", 0.0))
        alts       = routing.get("alternative_schemes", [])
        flags      = routing.get("risk_flags", [])
        missing    = routing.get("missing_parameters", [])

        # ── KarigarCred header bar ─────────────────────────────────────────────
        st.markdown(
            f"""<div class='kc-brand-header'>
              <div class='kc-brand-left'>
                <div class='kc-brand-logo'>◈</div>
                <div>
                  <div class='kc-brand-name'>KarigarCred</div>
                  <div class='kc-brand-sub'>Institutional Underwriting Terminal</div>
                </div>
              </div>
              <div class='kc-env-pill'>
                <span class='kc-env-dot'></span>
                LIVE &nbsp;·&nbsp; artisan_credit.db
                <span class='kc-env-sep'>/</span>
                Lucknow MSME cohort
              </div>
              <div class='kc-header-right'>
                <div class='kc-user-chip'>
                  <div class='kc-user-av'>BU</div>
                  <div>
                    <div class='kc-user-name'>{_display_name}</div>
                    <div class='kc-user-role'>{_role_tier}</div>
                  </div>
                </div>
              </div>
            </div>""",
            unsafe_allow_html=True,
        )

        # ── Cohort strip ───────────────────────────────────────────────────────
        @st.cache_data
        def _cohort_stats():
            conn = sqlite3.connect(DB_PATH)
            inv_count = pd.read_sql("SELECT COUNT(*) as c FROM gst_invoices", conn).iloc[0]["c"]
            led_count = pd.read_sql("SELECT COUNT(*) as c FROM order_ledgers", conn).iloc[0]["c"]
            art_count = pd.read_sql("SELECT COUNT(*) as c FROM artisans", conn).iloc[0]["c"]
            conn.close()
            return int(inv_count), int(led_count), int(art_count)

        _inv_c, _led_c, _art_c = _cohort_stats()
        st.markdown(
            f"""<div class='kc-cohort'>
              <div class='kc-cohort-cell'>
                <div class='kc-cohort-v'>{_art_c}</div>
                <div class='kc-cohort-k'>Portfolio</div>
                <div class='kc-cohort-s'>artisans scored</div>
              </div>
              <div class='kc-cohort-cell'>
                <div class='kc-cohort-v'>{_inv_c:,}</div>
                <div class='kc-cohort-k'>GST invoices</div>
                <div class='kc-cohort-s'>24-month window</div>
              </div>
              <div class='kc-cohort-cell'>
                <div class='kc-cohort-v'>{_led_c:,}</div>
                <div class='kc-cohort-k'>Ledger rows</div>
                <div class='kc-cohort-s'>digital khata</div>
              </div>
              <div class='kc-cohort-cell'>
                <div class='kc-cohort-v'>686</div>
                <div class='kc-cohort-k'>Mean score</div>
                <div class='kc-cohort-s'>501–790 range</div>
              </div>
              <div class='kc-cohort-cell'>
                <div class='kc-cohort-v'>{_art_c}/{_art_c}</div>
                <div class='kc-cohort-k'>Scheme-matched</div>
                <div class='kc-cohort-s'>hard-gate cleared</div>
              </div>
              <div class='kc-cohort-cov'>
                <div class='kc-cohort-cov-k'>Scheme coverage</div>
                <div class='kc-cov-track'><div class='kc-cov-fill' style='width:68%;background:var(--t-strong)'></div></div>
                <div class='kc-cov-lab'><span>MUDRA Kishor</span><span class='mono'>34</span></div>
                <div class='kc-cov-track'><div class='kc-cov-fill' style='width:28%;background:var(--t-std)'></div></div>
                <div class='kc-cov-lab'><span>MUDRA Shishu</span><span class='mono'>14</span></div>
                <div class='kc-cov-track'><div class='kc-cov-fill' style='width:4%;background:var(--accent)'></div></div>
                <div class='kc-cov-lab'><span>PM Vishwakarma</span><span class='mono'>2</span></div>
              </div>
            </div>""",
            unsafe_allow_html=True,
        )

        # ── Subject bar ────────────────────────────────────────────────────────
        craft_short = profile.craft_type.split()[0]
        st.markdown(
            f"""<div class='kc-subject'>
              <div>
                <div class='kc-subject-name'>{profile.name}</div>
                <div class='kc-subject-chips'>
                  <span class='kc-chip'>ART-{profile.artisan_id:04d}</span>
                  <span class='kc-chip'>{profile.cluster} Cluster</span>
                  <span class='kc-chip'>{profile.craft_type}</span>
                  <span class='kc-chip'>{profile.years_active} yrs active</span>
                  <span class='kc-chip'>Card: {profile.artisan_card_status}</span>
                </div>
              </div>
              <div class='kc-band-badge' style='border-color:{band_color};color:{band_color}'>
                <span class='kc-band-dot' style='background:{band_color}'></span>
                {band_tier} · {band_label}
              </div>
            </div>""",
            unsafe_allow_html=True,
        )

        # ── Executive Matrix — 6 columns ──────────────────────────────────────
        cap_value = fmt_inr(loan_amt) if loan_amt > 0 else "—"
        cap_sub   = rec_scheme or "No scheme matched"
        def_rate_col = "var(--t-sub)" if profile.severe_default_rate > 0.15 else "var(--t-prime)"
        st.markdown(
            f"""<div class='kc-exec'>
              <div class='kc-exec-cell accent'>
                <div class='kc-exec-k'>Composite Score</div>
                <div class='kc-exec-v' style='color:{band_color}'>{profile.credit_score}</div>
                <div class='kc-exec-s'>{band_label}</div>
              </div>
              <div class='kc-exec-cell'>
                <div class='kc-exec-k'>Algorithmic Confidence</div>
                <div class='kc-exec-v'>{confidence:.0%}</div>
                <div class='kc-exec-s'>router certainty</div>
              </div>
              <div class='kc-exec-cell'>
                <div class='kc-exec-k'>Capital Ceiling</div>
                <div class='kc-exec-v'>{cap_value}</div>
                <div class='kc-exec-s'>{cap_sub}</div>
              </div>
              <div class='kc-exec-cell'>
                <div class='kc-exec-k'>Prompt Settlement</div>
                <div class='kc-exec-v'>{profile.fast_payment_rate:.0%}</div>
                <div class='kc-exec-s'>0–60 day invoices</div>
              </div>
              <div class='kc-exec-cell'>
                <div class='kc-exec-k'>Default Rate</div>
                <div class='kc-exec-v' style='color:{def_rate_col}'>{profile.severe_default_rate:.1%}</div>
                <div class='kc-exec-s'>24-month window</div>
              </div>
              <div class='kc-exec-cell'>
                <div class='kc-exec-k'>Repeat-Buyer Share</div>
                <div class='kc-exec-v'>{profile.repeat_buyer_rate:.0%}</div>
                <div class='kc-exec-s'>order ledger</div>
              </div>
            </div>""",
            unsafe_allow_html=True,
        )

        # ── 60 / 40 split ─────────────────────────────────────────────────────
        left_col, right_col = st.columns([3, 2], gap="large")

        with left_col:
            # ── Score panel ───────────────────────────────────────────────────
            with st.container():
                st.markdown(
                    f"""<div class='kc-card' style='background:var(--surface);border:1px solid var(--border);
                        border-radius:11px;overflow:hidden;margin-bottom:14px'>
                      <div style='display:flex;align-items:baseline;justify-content:space-between;
                          padding:12px 15px;border-bottom:1px solid var(--border-2);font-size:12.5px;
                          font-weight:600;text-transform:uppercase;letter-spacing:.5px;color:var(--ink-2)'>
                        <span>Composite Credit Assessment</span>
                        <span style='font-size:11px;font-weight:500;text-transform:none;letter-spacing:0;
                            color:var(--muted);font-family:IBM Plex Mono,monospace'>300–850 · 30/40/30 weighting</span>
                      </div>
                    </div>""",
                    unsafe_allow_html=True,
                )
                _sp_l, _sp_r = st.columns([1, 1.4], gap="medium")
                with _sp_l:
                    st.plotly_chart(chart_gauge(profile.credit_score, band_color),
                                    use_container_width=True,
                                    config={"displayModeBar": False})
                with _sp_r:
                    st.plotly_chart(chart_subscores(profile),
                                    use_container_width=True,
                                    config={"displayModeBar": False})
                    st.caption(
                        f"Composite: **{profile.composite_raw:.1f}/100** → "
                        f"Score: **{profile.credit_score}** (300 + {profile.composite_raw:.1f}% × 550)"
                    )

            itab1, itab2, itab3 = st.tabs([
                "Signal Decomposition",
                "Invoicing Timeline",
                "Ledger SQL",
            ])

            # ── Inner Tab 1: Signal Decomposition ────────────────────────────
            with itab1:
                sc1, sc2, sc3 = st.columns(3, gap="small")

                _cf_g = sig_grade(profile.cashflow_score)
                with sc1:
                    st.markdown(
                        f"""<div class='kc-sig'>
                          <div class='kc-sig-top'>
                            <span class='kc-sig-t'>Cash-Flow Stability</span>
                            <span class='kc-sig-w'>30%</span>
                          </div>
                          <div class='kc-sig-score'>
                            <span class='kc-sig-v'>{profile.cashflow_score:.0f}</span>
                            <span class='kc-sig-d'>/100</span>
                            <span class='kc-sig-grade' data-g='{_cf_g}'>{_cf_g}</span>
                          </div>
                          <div class='kc-sig-rows'>
                            <div class='kc-sig-r'><span>Coefficient of variation</span><span>{profile.revenue_cv_adjusted:.2f}</span></div>
                            <div class='kc-sig-r'><span>Seasonality-adjusted</span><span>yes</span></div>
                            <div class='kc-sig-r'><span>Monthly turnover</span><span>{fmt_inr(profile.avg_monthly_revenue)}</span></div>
                          </div>
                        </div>""",
                        unsafe_allow_html=True,
                    )

                _ff_g = sig_grade(profile.fulfillment_score)
                with sc2:
                    st.markdown(
                        f"""<div class='kc-sig'>
                          <div class='kc-sig-top'>
                            <span class='kc-sig-t'>Invoice Fulfillment</span>
                            <span class='kc-sig-w'>40%</span>
                          </div>
                          <div class='kc-sig-score'>
                            <span class='kc-sig-v'>{profile.fulfillment_score:.0f}</span>
                            <span class='kc-sig-d'>/100</span>
                            <span class='kc-sig-grade' data-g='{_ff_g}'>{_ff_g}</span>
                          </div>
                          <div class='kc-sig-rows'>
                            <div class='kc-sig-r'><span>Prompt-settlement rate</span><span>{profile.fast_payment_rate:.0%}</span></div>
                            <div class='kc-sig-r'><span>Default rate</span><span>{profile.severe_default_rate:.1%}</span></div>
                            <div class='kc-sig-r'><span>Invoices on file</span><span>{profile.total_invoices}</span></div>
                          </div>
                        </div>""",
                        unsafe_allow_html=True,
                    )

                _rel_g = sig_grade(profile.relationship_score)
                with sc3:
                    st.markdown(
                        f"""<div class='kc-sig'>
                          <div class='kc-sig-top'>
                            <span class='kc-sig-t'>Trade Relationship</span>
                            <span class='kc-sig-w'>30%</span>
                          </div>
                          <div class='kc-sig-score'>
                            <span class='kc-sig-v'>{profile.relationship_score:.0f}</span>
                            <span class='kc-sig-d'>/100</span>
                            <span class='kc-sig-grade' data-g='{_rel_g}'>{_rel_g}</span>
                          </div>
                          <div class='kc-sig-rows'>
                            <div class='kc-sig-r'><span>Repeat-buyer share</span><span>{profile.repeat_buyer_rate:.0%}</span></div>
                            <div class='kc-sig-r'><span>Relationship tenure</span><span>{profile.years_active * 12} mo</span></div>
                            <div class='kc-sig-r'><span>Unique trade partners</span><span>{profile.unique_buyers}</span></div>
                          </div>
                        </div>""",
                        unsafe_allow_html=True,
                    )

            # ── Inner Tab 2: Invoicing Timeline ──────────────────────────────
            with itab2:
                st.markdown(
                    "<div class='section-header'>Monthly Revenue Consistency</div>",
                    unsafe_allow_html=True,
                )
                if not invoices.empty:
                    st.plotly_chart(chart_revenue(invoices), use_container_width=True,
                                    config={"displayModeBar": False})
                    st.caption(
                        f"Seasonality-adjusted CV: **{profile.revenue_cv_adjusted:.3f}** — "
                        "dashed line strips expected seasonal cycles to isolate genuine volatility."
                    )
                else:
                    st.markdown(
                        "<div class='empty-state'>"
                        "<div class='empty-icon'>◈</div>"
                        "<div class='empty-title'>No Invoice Data</div>"
                        "<div class='empty-sub'>No GST invoices found for this artisan.</div>"
                        "</div>",
                        unsafe_allow_html=True,
                    )

                st.markdown(
                    "<div class='section-header' style='margin-top:0.75rem'>"
                    "Invoice Payment Latency Distribution</div>",
                    unsafe_allow_html=True,
                )
                if not invoices.empty:
                    st.plotly_chart(chart_latency(invoices), use_container_width=True,
                                    config={"displayModeBar": False})
                    st.caption(
                        f"{profile.total_invoices} invoices &nbsp;·&nbsp; "
                        f"{profile.fast_payment_rate:.0%} within 45 d &nbsp;·&nbsp; "
                        f"{profile.severe_default_rate:.0%} severe defaults (>90 d)"
                    )

            # ── Inner Tab 3: Ledger SQL Logs ──────────────────────────────────
            with itab3:
                st.markdown(
                    "<div class='section-header'>GST Invoice History</div>",
                    unsafe_allow_html=True,
                )
                if not invoices.empty:
                    d = invoices.copy()
                    d["invoice_date"]  = d["invoice_date"].dt.strftime("%d %b %Y")
                    d["invoice_value"] = d["invoice_value"].apply(fmt_inr)
                    d["tax_paid"]      = d["tax_paid"].apply(fmt_inr)
                    d.columns = ["Date", "Buyer", "Invoice Value", "Tax Paid",
                                 "Status", "Delay (d)"]
                    st.dataframe(
                        d.head(30), use_container_width=True, hide_index=True,
                        column_config={"Delay (d)": st.column_config.NumberColumn(
                            "Delay (d)", format="%d d")},
                    )
                    st.caption(f"{len(invoices)} total invoices · showing most recent 30")
                else:
                    st.info("No invoice data on record.")

                st.markdown(
                    "<div class='section-header' style='margin-top:0.9rem'>"
                    "Digital Khata · Order Ledger</div>",
                    unsafe_allow_html=True,
                )
                if not ledger.empty:
                    d = ledger.copy()
                    d["order_value"]     = d["order_value"].apply(fmt_inr)
                    d["is_repeat_buyer"] = d["is_repeat_buyer"].map({1: "Yes", 0: "No"})
                    d.columns = ["Buyer", "Order Date", "Delivery Date", "Settlement Date",
                                 "Order Value", "Settlement (d)", "Repeat"]
                    st.dataframe(
                        d.head(30), use_container_width=True, hide_index=True,
                        column_config={"Settlement (d)": st.column_config.NumberColumn(
                            "Settlement (d)", format="%d d")},
                    )
                    st.caption(f"{len(ledger)} total entries · showing most recent 30")
                else:
                    st.info("No ledger data on record.")

        # ── RIGHT COLUMN — KarigarCred Underwriting Suite ─────────────────────
        with right_col:
            # Build alts HTML with colored dots
            _ALT_TONE_MAP = {
                "MUDRA Shishu":     "var(--t-std)",
                "MUDRA Kishor":     "var(--t-strong)",
                "MUDRA Tarun":      "var(--t-prime)",
                "PM Vishwakarma":   "var(--accent)",
                "ODOP Credit Line": "var(--muted)",
            }
            def _alt_dot_color(name):
                return _ALT_TONE_MAP.get(name, "var(--muted)")
            alts_items = "".join(
                f"<div class='kc-alt'>"
                f"<span class='kc-alt-dot' style='background:{_alt_dot_color(a)}'></span>"
                f"<span class='kc-alt-name'>{a}</span>"
                f"</div>"
                for a in alts
            ) if alts else "<div style='font-size:11.5px;color:var(--muted);font-style:italic'>No alternatives available</div>"

            flags_items = "".join(
                f"<div class='kc-callout-row'>{f}</div>" for f in flags
            ) if flags else f"<div class='kc-callout-empty'>No material risk signals.</div>"

            gaps_items = "".join(
                f"<div class='kc-callout-row'>{g}</div>" for g in missing
            ) if missing else f"<div class='kc-callout-empty'>All hard-gates cleared.</div>"

            _scheme_block = (
                f"<div class='kc-scheme-block'>"
                f"<div class='kc-scheme-eyebrow'>Recommended facility</div>"
                f"<div class='kc-scheme-name'>{rec_scheme}</div>"
                f"<div class='kc-scheme-amt'>{fmt_inr(loan_amt)}"
                f" <span>maximum capital ceiling</span></div>"
                f"<div class='kc-scheme-card'>Requires: GST + {profile.artisan_card_status} card</div>"
                f"<div style='margin-top:12px'>"
                f"<div class='kc-conf-row'><span>Match confidence</span><span>{confidence:.0%}</span></div>"
                f"<div class='kc-conf-track'><div class='kc-conf-fill' style='width:{confidence:.0%}'></div></div>"
                f"</div></div>"
            ) if rec_scheme else (
                f"<div class='kc-callout kc-callout--gap'>"
                f"<div style='font-size:13px;font-weight:600;color:var(--t-sub)'>No Eligible Scheme</div>"
                f"<div style='font-size:11.5px;color:var(--muted);margin-top:4px'>Review eligibility gaps below</div>"
                f"</div>"
            )

            # Header
            st.markdown(
                f"<div class='kc-uw-panel'>"
                f"<div class='kc-uw-hd'>"
                f"<span>Underwriting Suite</span>"
                f"<span class='kc-uw-tag' style='border-color:{band_color};color:{band_color}'>{band_tier}</span>"
                f"</div></div>",
                unsafe_allow_html=True,
            )
            # Scheme block
            st.markdown(_scheme_block, unsafe_allow_html=True)
            # Alternative facilities
            st.markdown(
                f"<div class='kc-uw-sec' style='margin-top:8px;margin-bottom:6px'>Alternative facilities</div>"
                + alts_items,
                unsafe_allow_html=True,
            )
            # Risk signals + eligibility gaps callouts
            st.markdown(
                f"<div class='kc-callouts-grid'>"
                f"<div class='kc-callout kc-callout--risk'>"
                f"<div class='kc-callout-hd'>Risk signals <em>{len(flags)}</em></div>"
                f"{flags_items}"
                f"</div>"
                f"<div class='kc-callout kc-callout--gap'>"
                f"<div class='kc-callout-hd'>Eligibility gaps <em>{len(missing)}</em></div>"
                f"{gaps_items}"
                f"</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

            st.markdown("<div style='height:0.4rem'></div>", unsafe_allow_html=True)
            if st.button("⬇ Export Underwriting Kit", use_container_width=True, type="primary",
                         key="export_kit_btn"):
                _log_action(_username, "UNDERWRITING_KIT_EXPORTED", profile.name, "DOWNLOADED")
            with st.expander("Raw Underwriting JSON"):
                _kit_json = json.dumps(routing, indent=2, ensure_ascii=False)
                _dl_col, _ = st.columns([1.4, 2])
                with _dl_col:
                    if st.download_button(
                        "📥 Download JSON",
                        data=_kit_json,
                        file_name=f"underwriting_{artisan_id:04d}.json",
                        mime="application/json",
                        key="dl_kit_btn",
                    ):
                        _log_action(
                            _username, "UNDERWRITING_KIT_EXPORTED",
                            profile.name, "DOWNLOADED",
                        )
                st.code(_kit_json, language="json")


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 2 — SMART ONBOARDING (all authenticated roles)
# ══════════════════════════════════════════════════════════════════════════════

with tab_onboard:
    # KarigarCred Field Assistant header
    st.markdown(
        f"""<div style='margin-bottom:16px'>
          <div style='font-size:11px;letter-spacing:2px;text-transform:uppercase;
              color:var(--muted);font-family:IBM Plex Mono,monospace'>KarigarCred · Field Onboarding</div>
          <div style='font-size:22px;font-weight:700;letter-spacing:-.3px;color:var(--ink);margin:6px 0 5px'>{tr['page_header']}</div>
          <div style='font-size:13.5px;color:var(--muted)'>{tr['page_sub']}</div>
        </div>""",
        unsafe_allow_html=True,
    )

    # ── Language segmented control ─────────────────────────────────────────────
    _ob_lang_key = st.session_state.get("ob_lang", "English")
    st.markdown("<div class='ob-lang-seg'>", unsafe_allow_html=True)
    _lb1, _lb2, _lb3 = st.columns(3)
    with _lb1:
        if st.button(tr["btn_en"], use_container_width=True, key="ob_lang_en",
                     type="primary" if lang == "English" else "secondary"):
            st.session_state["interface_lang"] = "English"
            st.session_state["onboard_analyzed"] = False
            st.rerun()
    with _lb2:
        if st.button(tr["btn_hi"], use_container_width=True, key="ob_lang_hi",
                     type="primary" if lang == "Hindi (हिन्दी)" else "secondary"):
            st.session_state["interface_lang"] = "Hindi (हिन्दी)"
            st.session_state["onboard_analyzed"] = False
            st.rerun()
    with _lb3:
        if st.button(tr["btn_aw"], use_container_width=True, key="ob_lang_aw",
                     type="primary" if lang == "Awadhi (अवधी)" else "secondary"):
            st.session_state["interface_lang"] = "Awadhi (अवधी)"
            st.session_state["onboard_analyzed"] = False
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    # ── Sample chips ───────────────────────────────────────────────────────────
    st.markdown(
        f"<div class='ob-sample-label'>{tr['sample_label']}</div>",
        unsafe_allow_html=True,
    )
    sb1, sb2, sb3, _pad = st.columns([1.3, 1.3, 1.3, 4.1])
    with sb1:
        if st.button(f"📄 {tr['btn_en']}", use_container_width=True, key="btn_samp_en"):
            st.session_state["onboard_text"]     = SAMPLES["English"]
            st.session_state["onboard_analyzed"] = False
    with sb2:
        if st.button(f"📄 {tr['btn_hi']}", use_container_width=True, key="btn_samp_hi"):
            st.session_state["onboard_text"]     = SAMPLES["Hindi (हिन्दी)"]
            st.session_state["onboard_analyzed"] = False
    with sb3:
        if st.button(f"📄 {tr['btn_aw']}", use_container_width=True, key="btn_samp_aw"):
            st.session_state["onboard_text"]     = SAMPLES["Awadhi (अवधी)"]
            st.session_state["onboard_analyzed"] = False

    # ── Text area ─────────────────────────────────────────────────────────────
    stmt = st.text_area(
        tr["input_label"],
        key="onboard_text",
        height=155,
        placeholder=tr["input_placeholder"],
    )

    ac1, _acpad = st.columns([1.6, 6.4])
    with ac1:
        analyze_clicked = st.button(
            tr["analyze_btn"], type="primary",
            use_container_width=True, key="btn_analyze",
        )

    if analyze_clicked:
        if stmt and stmt.strip():
            st.session_state["onboard_analyzed"] = True
            _log_action(
                _username, "STATEMENT_ANALYZED",
                (stmt[:60] + "…") if len(stmt) > 60 else stmt,
                "PARSED",
            )
        else:
            st.warning(tr["no_input_warn"])

    # ── Results or empty state ────────────────────────────────────────────────
    if st.session_state.get("onboard_analyzed") and stmt and stmt.strip():

        _slot = st.empty()
        _slot.markdown(
            f"<div class='ob-processing'>"
            f"<div class='ob-pulse'></div>"
            f"<span>{tr['processing']}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

        parsed   = parse_trade_statement(stmt)
        synth    = _build_synthetic_profile(parsed)
        ob_route = route_artisan(synth, DB_PATH)

        _slot.empty()
        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

        ob_left, ob_right = st.columns(2, gap="large")

        # ── Left card: extracted parameters (KarigarCred Field Assistant style) ─
        with ob_left:
            _nd   = tr["not_detected"]
            _dsuf = tr["days_suffix"]

            cluster_val  = parsed.cluster or _nd
            turnover_val = (fmt_inr(parsed.monthly_turnover) + " / mo") if parsed.monthly_turnover else _nd
            latency_val  = f"{parsed.payment_latency_days} {_dsuf}" if parsed.payment_latency_days else _nd
            loan_val     = fmt_inr(parsed.loan_amount) if parsed.loan_amount else _nd

            def _ob_check(ok: bool) -> str:
                return "<span class='ob-check-ok'>✓</span>" if ok else "<span class='ob-check-no'>✕</span>"

            _detected_count = sum([bool(parsed.cluster), bool(parsed.monthly_turnover),
                                   bool(parsed.payment_latency_days), bool(parsed.loan_amount)])

            st.markdown(
                f"""<div class='ob-card'>
                  <div class='ob-card-hd'>
                    <span class='ob-card-hd-t'>{tr['extracted_title']}</span>
                    <span class='ob-card-hd-b'>✓ {_detected_count} / 4</span>
                  </div>
                  <div class='ob-param-row'>
                    <span class='ob-param-key'>{tr['cluster_label']}</span>
                    <span class='ob-param-val {"detected" if parsed.cluster else "missing"}'>{cluster_val}</span>
                  </div>
                  <div class='ob-param-row'>
                    <span class='ob-param-key'>{tr['turnover_label']}</span>
                    <span class='ob-param-val {"detected" if parsed.monthly_turnover else "missing"}'>{turnover_val}</span>
                  </div>
                  <div class='ob-param-row'>
                    <span class='ob-param-key'>{tr['latency_label']}</span>
                    <span class='ob-param-val {"detected" if parsed.payment_latency_days else "missing"}'>{latency_val}</span>
                  </div>
                  <div class='ob-param-row'>
                    <span class='ob-param-key'>{tr['loan_req_label']}</span>
                    <span class='ob-param-val {"detected" if parsed.loan_amount else "missing"}'>{loan_val}</span>
                  </div>
                </div>""",
                unsafe_allow_html=True,
            )

            st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)
            st.markdown(
                "<div class='section-header'>Estimated Sub-Scores</div>",
                unsafe_allow_html=True,
            )
            ss1, ss2, ss3 = st.columns(3)
            with ss1:
                st.metric("Cash Flow",    f"{synth.cashflow_score:.0f}/100",
                          help="Inferred from payment latency → CV proxy")
            with ss2:
                st.metric("Fulfillment",  f"{synth.fulfillment_score:.0f}/100",
                          help="Fast-payment & default rates from latency bucket")
            with ss3:
                st.metric("Relationship", f"{synth.relationship_score:.0f}/100",
                          help="Conservative: 5yr tenure, 65% repeat buyer assumed")

        # ── Right card: localized agent recommendation ─────────────────────────
        with ob_right:
            ob_lbl, ob_css, ob_clr = score_meta(synth.credit_score)
            ob_tier  = score_tier(synth.credit_score)
            t_band   = tr["bands"].get(ob_lbl, ob_lbl)

            ob_scheme = ob_route.get("recommended_scheme")
            ob_loan   = float(ob_route.get("max_eligible_loan_amount", 0.0))
            ob_conf   = float(ob_route.get("confidence_score", 0.0))
            ob_alts   = ob_route.get("alternative_schemes", [])
            ob_flags  = [_t_flag(f, lang) for f in ob_route.get("risk_flags", [])]
            _raw_gaps = [_t_gap(g, lang)  for g in ob_route.get("missing_parameters", [])]
            ob_gaps   = list(dict.fromkeys(_raw_gaps))
            t_scheme  = tr["schemes"].get(ob_scheme, ob_scheme) if ob_scheme else None

            # Build callout rows
            _callout_rows = ""
            for f in ob_flags:
                _callout_rows += f"<div class='ob-flag-row'><span class='ob-co-risk'>!</span><span>{f}</span></div>"
            for g in ob_gaps:
                _callout_rows += f"<div class='ob-gap-row'><span class='ob-co-gap'>⚑</span><span>{g}</span></div>"
            if not ob_flags and not ob_gaps:
                _callout_rows = f"<div class='ob-flag-row'><span class='ob-co-ok'>✓</span><span style='color:var(--t-prime)'>{tr['none_label']}</span></div>"

            _scheme_section = (
                f"<div style='padding:12px 14px;border-bottom:1px solid var(--border-2)'>"
                f"<div style='font-size:10.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.4px'>{tr['scheme_label']}</div>"
                f"<div style='font-size:17px;font-weight:700;margin-top:3px;color:var(--ink)'>{t_scheme}</div>"
                f"<div style='font-family:IBM Plex Mono,monospace;font-size:13px;color:var(--ink-2);margin-top:3px'>{fmt_inr(ob_loan)} max</div>"
                f"</div>"
                f"<div style='padding:0 14px 12px'>"
                f"<div style='display:flex;justify-content:space-between;font-size:11.5px;font-weight:600;"
                f"color:var(--ink-2);margin-bottom:5px;margin-top:12px'>"
                f"<span>{tr['confidence_label']}</span>"
                f"<span style='font-family:IBM Plex Mono,monospace;color:var(--accent)'>{ob_conf:.0%}</span></div>"
                f"<div class='kc-conf-track'><div class='kc-conf-fill' style='width:{ob_conf:.0%}'></div></div>"
                f"</div>"
            ) if t_scheme else (
                f"<div style='padding:14px;color:var(--t-sub);font-size:13px;font-weight:600'>"
                f"No eligible scheme identified</div>"
            )

            st.markdown(
                f"""<div class='ob-card'>
                  <div class='ob-card-hd'><span class='ob-card-hd-t'>{tr['rec_title']}</span></div>
                  <div style='display:flex;align-items:center;gap:12px;padding:14px'>
                    <div style='text-align:center'>
                      <div class='ob-score-big' style='color:{ob_clr}'>{synth.credit_score}</div>
                      <div style='margin-top:4px'>
                        <span class='kc-band-badge' style='border-color:{ob_clr};color:{ob_clr};font-size:11px;padding:3px 8px'>
                          <span class='kc-band-dot' style='background:{ob_clr}'></span>
                          {ob_tier} · {t_band}
                        </span>
                      </div>
                    </div>
                  </div>
                  {_scheme_section}
                  <div style='border-top:1px solid var(--border-2)'>
                    {_callout_rows}
                  </div>
                </div>""",
                unsafe_allow_html=True,
            )

            st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
            if st.button(f"⬆ {tr.get('push', 'Push to underwriter')}", use_container_width=True,
                         key="ob_push_btn"):
                st.success(tr.get("pushed", "Sent to underwriting queue"))

        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        with st.expander("Raw Parser + Router JSON"):
            st.code(json.dumps({
                "parsed_statement": {
                    "cluster":              parsed.cluster,
                    "monthly_turnover":     parsed.monthly_turnover,
                    "payment_latency_days": parsed.payment_latency_days,
                    "loan_amount":          parsed.loan_amount,
                },
                "synthetic_credit_profile": {
                    "credit_score":        synth.credit_score,
                    "cashflow_score":      synth.cashflow_score,
                    "fulfillment_score":   synth.fulfillment_score,
                    "relationship_score":  synth.relationship_score,
                    "annual_turnover":     synth.annual_turnover,
                },
                "routing_output": ob_route,
            }, indent=2, ensure_ascii=False), language="json")

    else:
        st.markdown(
            f"""<div class='empty-state'>
            <div class='empty-icon'>◈</div>
            <div class='empty-title'>{tr['await_title']}</div>
            <div class='empty-sub'>{tr['await_sub']}</div>
            </div>""",
            unsafe_allow_html=True,
        )


# ══════════════════════════════════════════════════════════════════════════════
#  TAB — WHATSAPP BUSINESS SIMULATION SANDBOX  (all roles)
# ══════════════════════════════════════════════════════════════════════════════

with tab_wa:
    st.markdown(
        "<div class='section-header'>"
        "WhatsApp Business API · Live Credit Intelligence Ingestion Stream"
        "</div>",
        unsafe_allow_html=True,
    )

    # ── Session state defaults ────────────────────────────────────────────────
    for _k, _v in [
        ("wa_step", 0), ("wa_sample", None),
        ("wa_art_id", None), ("wa_inv_num", None),
    ]:
        if _k not in st.session_state:
            st.session_state[_k] = _v

    _wa_step    = st.session_state["wa_step"]
    _wa_sample  = st.session_state["wa_sample"]
    _wa_art_id  = st.session_state["wa_art_id"]
    _wa_inv_num = st.session_state["wa_inv_num"]

    wa_left, wa_right = st.columns([1.18, 1], gap="large")

    # ── Helper: render a single WhatsApp bubble ───────────────────────────────
    def _wa_bubble_in(text: str, ts: str) -> str:
        return (
            f"<div><div class='wa-in'>{text}</div>"
            f"<div class='wa-ts'>✓&nbsp;{ts}</div></div>"
        )

    def _wa_bubble_out(text: str, ts: str, attach: str = "") -> str:
        inner = f"<div class='wa-attach'>📎&nbsp;{attach}</div>" if attach else text
        return (
            f"<div style='display:flex;flex-direction:column;align-items:flex-end'>"
            f"<div class='wa-out'>{inner}</div>"
            f"<div class='wa-ts wa-ts-r'>✓✓&nbsp;{ts}</div></div>"
        )

    # ── Left column — smartphone UI ───────────────────────────────────────────
    with wa_left:

        # Build chat thread
        _chat = (
            "<div class='wa-divider'>Today</div>"
            + _wa_bubble_in(
                "नमस्कार! 🙏<br>"
                "अपना नया ऑर्डर या इनवॉइस का विवरण यहाँ भेजें।<br>"
                "<i style='color:#888;font-size:.72rem'>Hello! Send your new order or invoice "
                "details here — photo, voice note, or text.</i>",
                "10:02",
            )
            + _wa_bubble_out(
                "ठीक है! अभी bill की फोटो भेजता हूँ 📸<br>"
                "<i style='color:#555;font-size:.72rem'>Ok! Sending bill photo now.</i>",
                "10:04",
            )
            + _wa_bubble_in(
                "📸 <b>SmartScan™ Active</b><br>"
                "कृपया बिल या खाता बही की <b>स्पष्ट फोटो</b> भेजें।<br>"
                "<i style='color:#888;font-size:.72rem'>Please send a clear photo of the "
                "bill or Khata ledger.</i>",
                "10:05",
            )
        )

        if _wa_step == 1 and _wa_sample and _wa_sample in _WA_SAMPLES:
            _scan = _WA_SAMPLES[_wa_sample]
            _p    = parse_trade_statement(_scan["statement"])
            _chat += (
                _wa_bubble_out("", "10:06", attach=_scan["thumb"])
                + _wa_bubble_in(
                    "⚙️ <b>Vision Analytics Pipeline</b><br>"
                    "<code style='font-size:.65rem;color:#555'>"
                    "OCR → Language Parser → Credit Engine</code><br>"
                    "<i style='color:#888;font-size:.72rem'>Processing image…</i>",
                    "10:06",
                )
                + _wa_bubble_in(
                    f"✅ <b>Extraction Complete!</b><br><br>"
                    f"<b>Cluster:</b> {_p.cluster or _scan['cluster_hint']}<br>"
                    f"<b>Invoice Value:</b> ₹{_scan['invoice_value']:,.0f}<br>"
                    f"<b>Buyer:</b> {_scan['buyer']}<br>"
                    f"<b>Payment Terms:</b> {_scan['overdue_days']} days<br><br>"
                    f"<i style='color:#888;font-size:.72rem'>"
                    f"Syncing to credit database… ✓</i>",
                    "10:07",
                )
                + _wa_bubble_in(
                    f"🏦 <b>Database Updated!</b><br>"
                    f"Invoice <code>{_wa_inv_num}</code> recorded.<br>"
                    f"Credit score recalculated. Underwriter dashboard refreshed. 📊",
                    "10:07",
                )
                + _wa_bubble_out(
                    "बहुत अच्छा! शुक्रिया 🙏<br>"
                    "<i style='color:#555;font-size:.72rem'>Great! Thank you.</i>",
                    "10:08",
                )
            )

        st.markdown(
            f"""<div class='wa-phone'>
              <div class='wa-status'>
                <span>9:41 AM</span><span>▋▋▋&nbsp;WiFi&nbsp;🔋</span>
              </div>
              <div class='wa-header'>
                <span style='color:rgba(255,255,255,.7);font-size:1.1rem;margin-right:.2rem'>←</span>
                <div class='wa-avatar'>अ</div>
                <div>
                  <div class='wa-cname'>Artisan Credit Bot</div>
                  <div class='wa-cstat'>online&nbsp;·&nbsp;SmartScan™ enabled</div>
                </div>
                <span style='margin-left:auto;color:rgba(255,255,255,.65);font-size:1.2rem'>⋮</span>
              </div>
              <div class='wa-body'>{_chat}</div>
              <div class='wa-bar'>
                <span style='font-size:1rem;color:#777'>😊</span>
                <div class='wa-pill'>Type a message</div>
                <span style='font-size:1rem;color:#777'>📎</span>
                <div class='wa-send'>➤</div>
              </div>
            </div>""",
            unsafe_allow_html=True,
        )

    # ── Right column — OCR controls + extraction results ──────────────────────
    with wa_right:

        # Artisan picker
        _all_art     = load_artisan_list()
        _art_labels  = [
            f"{r['name']}  ·  {r['cluster']}  ·  {r['craft_type']}"
            for _, r in _all_art.iterrows()
        ]
        _art_pick = st.selectbox(
            "Simulating WhatsApp feed from artisan:",
            options=_art_labels,
            key="wa_artisan_pick",
        )
        _art_row   = _all_art.iloc[_art_labels.index(_art_pick)]
        _sel_art_id = int(_art_row["id"])

        st.markdown("<div style='height:0.2rem'></div>", unsafe_allow_html=True)

        st.markdown(
            "<div class='wa-ocr-hdr' style='margin-bottom:.6rem'>"
            "📎 Attach Bill / Ledger Image — OCR Simulation</div>",
            unsafe_allow_html=True,
        )

        _scan_pick = st.selectbox(
            "Select sample scan document:",
            options=list(_WA_SAMPLES.keys()),
            key="wa_scan_select",
        )

        st.markdown(
            "<div style='font-size:0.74rem;color:#475569;margin:.3rem 0 .7rem;line-height:1.55'>"
            "In production: artisan photographs their physical bill on WhatsApp. "
            "Our backend intercepts the media message and runs Vision OCR → "
            "Language Parser → Credit Engine in under 2 seconds.</div>",
            unsafe_allow_html=True,
        )

        _btn_col, _ = st.columns([1.4, 1])
        with _btn_col:
            _ingest_btn = st.button(
                "🚀 Simulate OCR Ingest →",
                type="primary",
                use_container_width=True,
                key="wa_ingest_btn",
            )

        if _ingest_btn:
            _chosen_scan = _WA_SAMPLES[_scan_pick]
            with st.spinner("Processing Image via Vision Analytics Pipeline…"):
                import time as _time_mod
                _time_mod.sleep(1.5)

            _new_inv = _wa_insert_invoice(
                _sel_art_id,
                _chosen_scan["buyer"],
                _chosen_scan["invoice_value"],
                _chosen_scan["overdue_days"],
            )
            _log_action(
                _username, "WHATSAPP_OCR_INGEST",
                _art_row["name"], f"Invoice:{_new_inv}",
            )
            st.session_state["wa_step"]    = 1
            st.session_state["wa_sample"]  = _scan_pick
            st.session_state["wa_art_id"]  = _sel_art_id
            st.session_state["wa_inv_num"] = _new_inv
            st.rerun()

        # ── Results panel (shown after processing) ────────────────────────────
        if _wa_step == 1 and _wa_sample and _wa_sample in _WA_SAMPLES:
            _scan_res = _WA_SAMPLES[_wa_sample]

            st.markdown(
                "<div class='wa-success'>"
                "<div class='wa-dot'></div>"
                "Database Updated Successfully via WhatsApp Stream! "
                "Underwriter Dashboard refreshed live."
                "</div>",
                unsafe_allow_html=True,
            )

            st.markdown("<div style='height:.65rem'></div>", unsafe_allow_html=True)

            # OCR raw text
            st.markdown(
                "<div class='wa-ocr-panel'>"
                "<div class='wa-ocr-hdr'>Extracted OCR Text Block</div>"
                f"<div class='wa-ocr-text'>{_scan_res['ocr_raw']}</div>"
                "</div>",
                unsafe_allow_html=True,
            )

            st.markdown("<div style='height:.55rem'></div>", unsafe_allow_html=True)

            # Parsed params + DB record summary
            _p_res   = parse_trade_statement(_scan_res["statement"])
            _s_res   = _build_synthetic_profile(_p_res)
            _art_name_res = _all_art[_all_art["id"] == _wa_art_id]["name"].values
            _art_name_str = _art_name_res[0] if len(_art_name_res) else "—"

            _kv_rows = [
                ("Cluster Detected",   _p_res.cluster or _scan_res["cluster_hint"]),
                ("Monthly Turnover",   fmt_inr(_p_res.monthly_turnover) if _p_res.monthly_turnover else "—"),
                ("Payment Latency",    f"{_p_res.payment_latency_days} d" if _p_res.payment_latency_days else "—"),
                ("Invoice Value",      fmt_inr(_scan_res["invoice_value"])),
                ("Buyer",              _scan_res["buyer"]),
                ("Est. Credit Score",  str(_s_res.credit_score)),
                ("Inserted Invoice #", _wa_inv_num or "—"),
                ("Artisan Record",     _art_name_str),
            ]
            _kv_html = "".join(
                f"<div class='wa-kv'>"
                f"<span class='wa-kv-k'>{k}</span>"
                f"<span class='wa-kv-v'>{v}</span>"
                f"</div>"
                for k, v in _kv_rows
            )
            st.markdown(
                f"<div class='wa-ocr-panel'>"
                f"<div class='wa-ocr-hdr'>Language Parser · Extracted Parameters</div>"
                f"{_kv_html}"
                f"</div>",
                unsafe_allow_html=True,
            )

            st.markdown(
                "<div style='font-size:.72rem;color:#475569;margin-top:.65rem;line-height:1.6'>"
                "Switch to <b>📊 Credit Dashboard</b> and select <b>"
                + _art_name_str
                + "</b> — the invoice count and recalculated credit score "
                "reflect the new record <b>instantly</b>."
                "</div>",
                unsafe_allow_html=True,
            )

            st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
            if st.button("↺ Reset Sandbox", key="wa_reset_btn"):
                for _k in ("wa_step", "wa_sample", "wa_art_id", "wa_inv_num"):
                    st.session_state[_k] = None if _k != "wa_step" else 0
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 3 — AUDIT LOGS  (Bank Underwriter only)
# ══════════════════════════════════════════════════════════════════════════════

if _is_manager:
    with tab_audit:
        st.markdown(
            "<div class='section-header'>Governance & Audit Trail</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div style='font-size:0.82rem;color:#475569;margin-bottom:0.6rem'>"
            "Append-only telemetry log — records every credit computation, "
            "statement parse, and kit export. Cleared only on full database reset."
            "</div>",
            unsafe_allow_html=True,
        )

        audit_df = _load_audit_logs()

        if not audit_df.empty:
            # Summary stats row
            _unique_users   = audit_df["username"].nunique()
            _total_events   = len(audit_df)
            _score_events   = int((audit_df["action"] == "CREDIT_SCORE_VIEWED").sum())
            _parse_events   = int((audit_df["action"] == "STATEMENT_ANALYZED").sum())
            _export_events  = int((audit_df["action"] == "UNDERWRITING_KIT_EXPORTED").sum())

            ac1, ac2, ac3, ac4 = st.columns(4, gap="small")
            with ac1:
                st.markdown(
                    f"<div class='audit-stat'>"
                    f"<div class='audit-stat-val'>{_total_events}</div>"
                    f"<div class='audit-stat-lbl'>Total Events</div>"
                    f"</div>", unsafe_allow_html=True,
                )
            with ac2:
                st.markdown(
                    f"<div class='audit-stat'>"
                    f"<div class='audit-stat-val'>{_score_events}</div>"
                    f"<div class='audit-stat-lbl'>Scores Viewed</div>"
                    f"</div>", unsafe_allow_html=True,
                )
            with ac3:
                st.markdown(
                    f"<div class='audit-stat'>"
                    f"<div class='audit-stat-val'>{_parse_events}</div>"
                    f"<div class='audit-stat-lbl'>Statements Parsed</div>"
                    f"</div>", unsafe_allow_html=True,
                )
            with ac4:
                st.markdown(
                    f"<div class='audit-stat'>"
                    f"<div class='audit-stat-val'>{_export_events}</div>"
                    f"<div class='audit-stat-lbl'>Kits Exported</div>"
                    f"</div>", unsafe_allow_html=True,
                )

            st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)

            audit_df.columns = ["Timestamp (UTC)", "User", "Action", "Artisan Target", "Result Status"]
            st.dataframe(
                audit_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Timestamp (UTC)":  st.column_config.TextColumn("Timestamp (UTC)",  width="large"),
                    "User":             st.column_config.TextColumn("User",             width="small"),
                    "Action":           st.column_config.TextColumn("Action",           width="medium"),
                    "Artisan Target":   st.column_config.TextColumn("Artisan Target",   width="large"),
                    "Result Status":    st.column_config.TextColumn("Result Status",    width="medium"),
                },
            )
            st.caption(f"{_total_events} total audit events · {_unique_users} distinct user(s) · most recent first")

        else:
            st.markdown(
                "<div class='empty-state'>"
                "<div class='empty-icon'>◈</div>"
                "<div class='empty-title'>No Audit Events Yet</div>"
                "<div class='empty-sub'>"
                "Events are recorded automatically when credit scores are viewed, "
                "statements are analyzed, or underwriting kits are exported."
                "</div>"
                "</div>",
                unsafe_allow_html=True,
            )
