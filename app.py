"""
app.py
------
Enterprise fintech dashboard — Lucknow Artisan Alternative Credit Scoring System.

Run:      streamlit run app.py
Requires: artisan_credit.db  (python3 main.py first)
Packages: streamlit, plotly, pandas, numpy
"""

import json
import os
import re
import sqlite3

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
st.markdown("""
<style>
/* ── Base ─────────────────────────────────────────────────────────── */
[data-testid="stAppViewContainer"],
[data-testid="stMain"] { background: #0E1117 !important; }
.block-container         { padding-top: 1.4rem !important; padding-bottom: 1rem; max-width: 1440px; }
html, body               { font-family: 'Inter', 'Segoe UI', sans-serif; }

/* ── Sidebar ─────────────────────────────────────────────────────── */
[data-testid="stSidebar"]          { background: #13161E !important; border-right: 1px solid #2E323D; }
[data-testid="stSidebar"] *        { color: #94A3B8 !important; }
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] strong   { color: #F1F5F9 !important; }
[data-testid="stSidebar"] .stMarkdown p { font-size: 0.82rem; }
[data-testid="stSidebar"] [data-testid="stMetricValue"]  { color: #38BDF8 !important; font-size: 1rem !important; }
[data-testid="stSidebar"] [data-testid="stMetricLabel"]  { color: #64748B !important; }

/* ── Tab strip ───────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"]  {
    background: transparent !important;
    border-bottom: 1px solid #2E323D !important;
    gap: 0.15rem;
    padding-bottom: 0;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: #475569 !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.04em;
    border-radius: 6px 6px 0 0 !important;
    padding: 0.55rem 1.1rem !important;
    border-bottom: 2px solid transparent !important;
}
.stTabs [aria-selected="true"] {
    color: #38BDF8 !important;
    border-bottom: 2px solid #38BDF8 !important;
    background: rgba(56,189,248,0.04) !important;
}
.stTabs [data-baseweb="tab-panel"] { padding-top: 1rem; }

/* ── Progress bar ────────────────────────────────────────────────── */
.stProgress > div                  { background: #2E323D !important; border-radius: 9999px; height: 8px !important; }
.stProgress > div > div            { background: linear-gradient(90deg,#0EA5E9,#38BDF8) !important; border-radius: 9999px; }

/* ── Metric delta hide ───────────────────────────────────────────── */
[data-testid="stMetricDelta"] svg  { display:none; }

/* ── Expander ─────────────────────────────────────────────────────── */
[data-testid="stExpander"]         { background: #13161E !important; border: 1px solid #2E323D !important; border-radius: 10px !important; }
[data-testid="stExpander"] summary { color: #64748B !important; font-size: 0.78rem; }

/* ── Code block ───────────────────────────────────────────────────── */
.stCodeBlock code { font-size: 0.72rem !important; }

/* ─────────────────────────────────────────────────────────────────────────
   LAYOUT PRIMITIVES
───────────────────────────────────────────────────────────────────────── */
.section-header {
    font-size: 0.62rem; font-weight: 700; letter-spacing: 0.14em;
    text-transform: uppercase; color: #475569;
    padding-bottom: 0.5rem; margin-bottom: 0.75rem;
    border-bottom: 1px solid #2E323D;
}

.fin-card {
    background: #1A1D24; border: 1px solid #2E323D;
    border-radius: 12px; padding: 1.25rem 1.5rem;
}

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
.exec-metric {
    background: linear-gradient(145deg,#1A1D24 0%,#22262F 100%);
    border: 1px solid #2E323D; border-radius: 12px;
    padding: 1.2rem 1.4rem; text-align: center; height: 100%;
}
.exec-metric .em-label {
    font-size: 0.6rem; font-weight: 700; letter-spacing: 0.15em;
    text-transform: uppercase; color: #475569; margin-bottom: 0.55rem;
}
.exec-metric .em-value {
    font-size: 2rem; font-weight: 900; line-height: 1;
    letter-spacing: -0.03em;
}
.exec-metric .em-sub {
    font-size: 0.7rem; color: #475569; margin-top: 0.35rem;
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
.risk-prime  { background: rgba(16,185,129,0.12); color: #10B981; border: 1px solid rgba(16,185,129,0.3); }
.risk-near   { background: rgba(56,189,248,0.12); color: #38BDF8; border: 1px solid rgba(56,189,248,0.3); }
.risk-sub    { background: rgba(245,158,11,0.12);  color: #F59E0B; border: 1px solid rgba(245,158,11,0.3); }
.risk-deep   { background: rgba(239,68,68,0.12);   color: #EF4444; border: 1px solid rgba(239,68,68,0.3); }
.risk-invis  { background: rgba(129,140,248,0.12); color: #818CF8; border: 1px solid rgba(129,140,248,0.3); }

/* ─────────────────────────────────────────────────────────────────────────
   SIGNAL DECOMPOSITION CARDS
───────────────────────────────────────────────────────────────────────── */
.signal-card {
    background: #13161E; border: 1px solid #2E323D;
    border-radius: 10px; padding: 1rem 1.1rem; height: 100%;
}
.signal-label {
    font-size: 0.6rem; font-weight: 700; letter-spacing: 0.13em;
    text-transform: uppercase; color: #475569; margin-bottom: 0.4rem;
}
.signal-score {
    font-size: 2.2rem; font-weight: 900; line-height: 1;
    letter-spacing: -0.03em; margin-bottom: 0.08rem;
}
.signal-denom { font-size: 0.85rem; color: #475569; }
.signal-weight { font-size: 0.68rem; color: #374151; margin-bottom: 0.6rem; }
.signal-kv {
    display: flex; justify-content: space-between;
    font-size: 0.76rem; color: #64748B;
    padding: 0.28rem 0; border-bottom: 1px solid #1E2229;
}
.signal-kv:last-of-type { border-bottom: none; }
.signal-kv-val { font-weight: 700; }
.sig-grade {
    font-size: 0.6rem; font-weight: 700; letter-spacing: 0.1em;
    text-transform: uppercase; padding: 0.12rem 0.45rem;
    border-radius: 4px;
}

/* ─────────────────────────────────────────────────────────────────────────
   UNDERWRITING SUITE (right column)
───────────────────────────────────────────────────────────────────────── */
.scheme-block {
    background: linear-gradient(135deg,rgba(16,185,129,0.09) 0%,rgba(16,185,129,0.03) 100%);
    border: 1px solid rgba(16,185,129,0.25); border-radius: 12px;
    padding: 1.3rem 1.5rem;
}
.scheme-amount {
    font-size: 2.2rem; font-weight: 900; color: #10B981;
    line-height: 1; letter-spacing: -0.03em;
}
.flag-item {
    background: rgba(245,158,11,0.07); border-left: 3px solid #F59E0B;
    border-radius: 0 6px 6px 0; padding: 0.42rem 0.75rem;
    margin-bottom: 0.3rem; font-size: 0.78rem; color: #FCD34D;
}
.gap-item {
    background: rgba(239,68,68,0.07); border-left: 3px solid #EF4444;
    border-radius: 0 6px 6px 0; padding: 0.42rem 0.75rem;
    margin-bottom: 0.3rem; font-size: 0.78rem; color: #FCA5A5;
}
.alt-row {
    font-size: 0.78rem; color: #64748B; padding: 0.3rem 0;
    border-bottom: 1px solid #1E2229;
}
.underwrite-kv {
    display: flex; justify-content: space-between; align-items: center;
    padding: 0.35rem 0; border-bottom: 1px solid #1E2229;
    font-size: 0.79rem;
}
.underwrite-kv-key { color: #64748B; }
.underwrite-kv-val { font-weight: 700; color: #F1F5F9; }

/* ─────────────────────────────────────────────────────────────────────────
   ONBOARDING (dark)
───────────────────────────────────────────────────────────────────────── */
.ob-sample-label {
    font-size: 0.6rem; font-weight: 700; letter-spacing: 0.13em;
    text-transform: uppercase; color: #475569;
    margin-bottom: 0.5rem; margin-top: 0.2rem;
}
.ob-card {
    background: #1A1D24; border: 1px solid #2E323D;
    border-radius: 12px; padding: 1.4rem 1.6rem; height: 100%;
}
.ob-card-title {
    font-size: 0.6rem; font-weight: 700; letter-spacing: 0.12em;
    text-transform: uppercase; color: #475569;
    padding-bottom: 0.5rem; margin-bottom: 0.8rem;
    border-bottom: 1px solid #2E323D;
}
.ob-param-row {
    display: flex; justify-content: space-between; align-items: center;
    padding: 0.58rem 0; border-bottom: 1px solid #1E2229;
    font-size: 0.84rem;
}
.ob-param-row:last-child { border-bottom: none; }
.ob-param-key  { color: #64748B; }
.ob-param-val  { font-weight: 700; color: #F1F5F9; text-align: right; }
.ob-param-val.detected { color: #10B981; }
.ob-param-val.missing  { color: #374151; font-style: italic; font-weight: 400; }
.ob-score-big  { font-size: 3rem; font-weight: 900; text-align: center; line-height: 1.1; }
.ob-flag-row {
    background: rgba(245,158,11,0.07); border-left: 3px solid #F59E0B;
    border-radius: 0 6px 6px 0; padding: 0.38rem 0.7rem;
    margin-bottom: 0.28rem; font-size: 0.77rem; color: #FCD34D;
}
.ob-gap-row {
    background: rgba(239,68,68,0.07); border-left: 3px solid #EF4444;
    border-radius: 0 6px 6px 0; padding: 0.38rem 0.7rem;
    margin-bottom: 0.28rem; font-size: 0.77rem; color: #FCA5A5;
}
.ob-processing {
    display: flex; align-items: center; gap: 0.8rem;
    background: rgba(56,189,248,0.05); border: 1px solid rgba(56,189,248,0.2);
    border-radius: 10px; padding: 0.85rem 1.3rem;
    font-size: 0.86rem; color: #38BDF8; font-weight: 500;
}
.ob-pulse {
    width: 10px; height: 10px; border-radius: 50%;
    background: #38BDF8; flex-shrink: 0;
    animation: ob-anim 1.2s ease-in-out infinite;
}
@keyframes ob-anim {
    0%,100% { transform: scale(1); opacity: 1; }
    50%      { transform: scale(1.7); opacity: 0.3; }
}

/* ─────────────────────────────────────────────────────────────────────────
   EMPTY STATE
───────────────────────────────────────────────────────────────────────── */
.empty-state {
    text-align: center; padding: 3.5rem 1.5rem;
    background: #13161E; border: 1px dashed #2E323D;
    border-radius: 12px; margin: 0.5rem 0;
}
.empty-icon  { font-size: 2.2rem; color: #2E323D; margin-bottom: 0.7rem; }
.empty-title { font-size: 0.95rem; font-weight: 700; color: #475569; margin-bottom: 0.4rem; }
.empty-sub   { font-size: 0.8rem; color: #374151; max-width: 360px; margin: 0 auto; line-height: 1.55; }

/* ── Hide Streamlit chrome ───────────────────────────────────────── */
#MainMenu { visibility: hidden; }
footer     { visibility: hidden; }
header     { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


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


# ──────────────────────────────────────────────────────────────────────────────
# Core helpers
# ──────────────────────────────────────────────────────────────────────────────

def fmt_inr(v: float) -> str:
    if v >= 1_00_00_000: return f"₹{v/1_00_00_000:.2f} Cr"
    if v >= 1_00_000:    return f"₹{v/1_00_000:.2f} L"
    if v >= 1_000:       return f"₹{v/1_000:.1f} K"
    return f"₹{v:.0f}"


def score_meta(s: int) -> tuple[str, str, str]:
    """Returns (label, badge-css-class, hex-color)."""
    if s >= 750: return "Prime",            "risk-prime", "#10B981"
    if s >= 650: return "Near-Prime",       "risk-near",  "#38BDF8"
    if s >= 550: return "Subprime",         "risk-sub",   "#F59E0B"
    if s >= 450: return "Deep Subprime",    "risk-deep",  "#EF4444"
    return               "Credit Invisible","risk-invis",  "#818CF8"


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


# ──────────────────────────────────────────────────────────────────────────────
# Dark-mode Plotly charts
# ──────────────────────────────────────────────────────────────────────────────

_DARK_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter,sans-serif", color="#94A3B8"),
)
_AXIS_STYLE = dict(
    showgrid=True, gridcolor="#1E2229",
    tickfont=dict(size=9, color="#64748B"),
    linecolor="#2E323D", tickcolor="#2E323D",
)


def chart_gauge(score: int, color: str) -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number={"font": {"size": 48, "color": color, "family": "Inter,sans-serif"}},
        gauge={
            "axis": {
                "range": [300, 850],
                "tickvals": [300, 450, 550, 650, 750, 850],
                "tickfont": {"size": 8, "color": "#475569"},
                "tickcolor": "#2E323D",
            },
            "bar":       {"color": color, "thickness": 0.22},
            "bgcolor":   "rgba(0,0,0,0)",
            "borderwidth": 0,
            "steps": [
                {"range": [300, 450], "color": "rgba(239,68,68,0.10)"},
                {"range": [450, 550], "color": "rgba(245,158,11,0.10)"},
                {"range": [550, 650], "color": "rgba(234,179,8,0.10)"},
                {"range": [650, 750], "color": "rgba(56,189,248,0.10)"},
                {"range": [750, 850], "color": "rgba(16,185,129,0.10)"},
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
    colors = ["#38BDF8", "#10B981", "#818CF8"]

    fig = go.Figure(go.Bar(
        y=cats, x=vals, orientation="h",
        marker_color=colors,
        text=[f"{v:.0f}" for v in vals],
        textposition="inside", insidetextanchor="middle",
        textfont={"size": 11, "color": "white", "family": "Inter,sans-serif"},
        hovertemplate="%{y}: %{x:.1f}/100<extra></extra>",
    ))
    fig.add_vline(
        x=profile.composite_raw, line_dash="dot",
        line_color="#94A3B8", line_width=1.5,
        annotation_text=f"  {profile.composite_raw:.0f}",
        annotation_position="top right",
        annotation_font_size=9, annotation_font_color="#94A3B8",
    )
    fig.update_layout(
        xaxis=dict(range=[0, 100], title="", **_AXIS_STYLE),
        yaxis=dict(showgrid=False, tickfont={"size": 9, "color": "#94A3B8"}),
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
        line=dict(color="#38BDF8", width=2.5), marker=dict(size=4),
        fill="tozeroy", fillcolor="rgba(56,189,248,0.06)",
        hovertemplate="%{x}: ₹%{y:,.0f}<extra>Actual</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=m_adj["year_month"], y=m_adj["adj_value"],
        mode="lines", name="Seasonality-Adjusted",
        line=dict(color="#475569", width=1.5, dash="dot"),
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
    labels = ["0–15d\nPrompt", "16–30d\nStandard", "31–45d\nLate",
              "46–90d\nOverdue", "91+d\nDefault"]
    counts = [
        int((od <= 15).sum()),
        int(((od > 15) & (od <= 30)).sum()),
        int(((od > 30) & (od <= 45)).sum()),
        int(((od > 45) & (od <= 90)).sum()),
        int((od > 90).sum()),
    ]
    pcts   = [f"{c / total:.0%}" for c in counts]
    colors = ["#10B981", "#38BDF8", "#F59E0B", "#F97316", "#EF4444"]

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
# Sidebar — language + artisan selector
# ──────────────────────────────────────────────────────────────────────────────

all_artisans = load_artisan_list()

with st.sidebar:
    lang = st.radio(
        "Language / भाषा",
        ["English", "Hindi (हिन्दी)", "Awadhi (अवधी)"],
        horizontal=True,
        key="interface_lang",
    )
    tr = TRANSLATIONS[lang]

    st.divider()
    st.markdown("## Artisan Directory")
    st.caption(f"{len(all_artisans)} artisans · Lucknow")

    search      = st.text_input("", placeholder="Search by name…",
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
    st.markdown(f"**{chosen_row['name']}**")
    st.markdown(
        f"<span style='font-size:0.78rem;color:#64748B'>"
        f"{chosen_row['cluster']} · {chosen_row['craft_type']}</span>",
        unsafe_allow_html=True,
    )
    st.metric("Annual Turnover", fmt_inr(float(chosen_row["annual_turnover"])))
    st.metric("Card Status",     chosen_row["artisan_card_status"])


# ──────────────────────────────────────────────────────────────────────────────
# Main tab bar
# ──────────────────────────────────────────────────────────────────────────────

tab_dash, tab_onboard = st.tabs([tr["dashboard_tab"], tr["onboarding_tab"]])


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 1 — CREDIT DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

with tab_dash:
    profile   = load_profile(artisan_id)
    routing   = load_routing(artisan_id)
    invoices  = load_invoices(artisan_id)
    ledger    = load_ledger(artisan_id)

    band_label, band_css, band_color = score_meta(profile.credit_score)

    rec_scheme = routing.get("recommended_scheme")
    loan_amt   = float(routing.get("max_eligible_loan_amount", 0.0))
    confidence = float(routing.get("confidence_score", 0.0))
    alts       = routing.get("alternative_schemes", [])
    flags      = routing.get("risk_flags", [])
    missing    = routing.get("missing_parameters", [])

    # ── Header bar ────────────────────────────────────────────────────────────
    st.markdown(
        f"""<div class='dash-header'>
        <div>
          <div class='dash-header-name'>{profile.name}</div>
          <div class='dash-header-sub'>
            {profile.craft_type}&nbsp;·&nbsp;{profile.cluster} Cluster
            &nbsp;·&nbsp;{profile.years_active} yrs active
            &nbsp;·&nbsp;Card:&nbsp;{profile.artisan_card_status}
          </div>
        </div>
        <div class='dash-header-right'>
          <span class='risk-badge {band_css}'>{band_label}</span>
          <span style='font-size:0.7rem;color:#374151'>ID&nbsp;#{profile.artisan_id:04d}</span>
        </div>
        </div>""",
        unsafe_allow_html=True,
    )

    # ── Executive Summary Matrix ───────────────────────────────────────────────
    em1, em2, em3, em4 = st.columns(4, gap="small")

    with em1:
        st.markdown(
            f"""<div class='exec-metric'>
            <div class='em-label'>Alternative Credit Score</div>
            <div class='em-value' style='color:{band_color}'>{profile.credit_score}</div>
            <div class='em-sub'>Range 300–850 &nbsp;·&nbsp; CIBIL-aligned</div>
            </div>""",
            unsafe_allow_html=True,
        )
    with em2:
        st.markdown(
            f"""<div class='exec-metric'>
            <div class='em-label'>Algorithmic Confidence</div>
            <div class='em-value' style='color:#38BDF8'>{confidence:.0%}</div>
            <div class='em-sub'>{profile.total_invoices} invoices&nbsp;·&nbsp;{profile.unique_buyers} buyers</div>
            </div>""",
            unsafe_allow_html=True,
        )
    with em3:
        cap_value = fmt_inr(loan_amt) if loan_amt > 0 else "—"
        cap_sub   = rec_scheme or "No scheme matched"
        st.markdown(
            f"""<div class='exec-metric'>
            <div class='em-label'>Recommended Capital Ceiling</div>
            <div class='em-value' style='color:#10B981'>{cap_value}</div>
            <div class='em-sub'>{cap_sub}</div>
            </div>""",
            unsafe_allow_html=True,
        )
    with em4:
        st.markdown(
            f"""<div class='exec-metric'>
            <div class='em-label'>Prompt Settlement Rate</div>
            <div class='em-value' style='color:#F59E0B'>{profile.fast_payment_rate:.0%}</div>
            <div class='em-sub'>Invoices cleared within 45 days</div>
            </div>""",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)

    # ── 60 / 40 split ─────────────────────────────────────────────────────────
    left_col, right_col = st.columns([3, 2], gap="large")

    # ┌─────────────────────────────────────────────────────────────────────────
    # │  LEFT COLUMN — Data Dossier with 3 inner tabs
    # └─────────────────────────────────────────────────────────────────────────
    with left_col:
        itab1, itab2, itab3 = st.tabs([
            "📊 Multilingual Parser",
            "📈 Invoicing Timeline",
            "🗃️ Ledger SQL Logs",
        ])

        # ── Inner Tab 1: Score Signal Analysis ────────────────────────────────
        with itab1:
            g_col, s_col = st.columns([1, 1.35], gap="medium")

            with g_col:
                st.markdown("<div class='section-header'>Credit Score</div>",
                            unsafe_allow_html=True)
                st.plotly_chart(chart_gauge(profile.credit_score, band_color),
                                use_container_width=True,
                                config={"displayModeBar": False})
                st.markdown(
                    f"<div style='text-align:center;margin-top:-0.6rem'>"
                    f"<span class='risk-badge {band_css}'>{band_label}</span></div>",
                    unsafe_allow_html=True,
                )

            with s_col:
                st.markdown("<div class='section-header'>Score Breakdown</div>",
                            unsafe_allow_html=True)
                st.plotly_chart(chart_subscores(profile),
                                use_container_width=True,
                                config={"displayModeBar": False})
                st.caption(
                    f"Composite: **{profile.composite_raw:.1f} / 100**  "
                    f"→ Final score: **{profile.credit_score}** "
                    f"(300 + {profile.composite_raw:.1f}% × 550)"
                )

            st.markdown("<div style='height:0.25rem'></div>", unsafe_allow_html=True)
            st.markdown(
                "<div class='section-header'>Alternative Data Signal Decomposition</div>",
                unsafe_allow_html=True,
            )

            sc1, sc2, sc3 = st.columns(3, gap="small")

            # Cash Flow signal
            cf_grade = "STABLE" if profile.revenue_cv_adjusted < 0.30 else (
                       "VOLATILE" if profile.revenue_cv_adjusted > 0.60 else "MODERATE")
            cf_g_clr = ("#10B981" if profile.revenue_cv_adjusted < 0.30 else
                        "#EF4444" if profile.revenue_cv_adjusted > 0.60 else "#F59E0B")
            with sc1:
                st.markdown(
                    f"""<div class='signal-card'>
                    <div class='signal-label'>Cash Flow Signal</div>
                    <div class='signal-score' style='color:#818CF8'>
                        {profile.cashflow_score:.1f}
                        <span class='signal-denom'>/100</span>
                    </div>
                    <div class='signal-weight'>Weight 30% &nbsp;·&nbsp; S_CF</div>
                    <div class='signal-kv'>
                        <span>CV<sub>adj</sub></span>
                        <span class='signal-kv-val'>{profile.revenue_cv_adjusted:.3f}</span>
                    </div>
                    <div class='signal-kv'>
                        <span>Avg Monthly</span>
                        <span class='signal-kv-val'>{fmt_inr(profile.avg_monthly_revenue)}</span>
                    </div>
                    <div class='signal-kv'>
                        <span>Volatility</span>
                        <span class='sig-grade' style='color:{cf_g_clr}'>{cf_grade}</span>
                    </div>
                    </div>""",
                    unsafe_allow_html=True,
                )

            # Fulfillment signal
            ff_grade = ("EXCELLENT" if profile.fast_payment_rate >= 0.80 else
                        "POOR" if profile.fast_payment_rate < 0.40 else "FAIR")
            ff_g_clr = ("#10B981" if profile.fast_payment_rate >= 0.80 else
                        "#EF4444" if profile.fast_payment_rate < 0.40 else "#F59E0B")
            with sc2:
                st.markdown(
                    f"""<div class='signal-card'>
                    <div class='signal-label'>Fulfillment Signal</div>
                    <div class='signal-score' style='color:#10B981'>
                        {profile.fulfillment_score:.1f}
                        <span class='signal-denom'>/100</span>
                    </div>
                    <div class='signal-weight'>Weight 40% &nbsp;·&nbsp; S_FF</div>
                    <div class='signal-kv'>
                        <span>Fast Rate</span>
                        <span class='signal-kv-val'>{profile.fast_payment_rate:.0%}</span>
                    </div>
                    <div class='signal-kv'>
                        <span>Default Rate</span>
                        <span class='signal-kv-val'>{profile.severe_default_rate:.0%}</span>
                    </div>
                    <div class='signal-kv'>
                        <span>Settlement</span>
                        <span class='sig-grade' style='color:{ff_g_clr}'>{ff_grade}</span>
                    </div>
                    </div>""",
                    unsafe_allow_html=True,
                )

            # Relationship signal
            rel_grade = ("STRONG"   if profile.repeat_buyer_rate >= 0.70 else
                         "WEAK"     if profile.repeat_buyer_rate < 0.30 else "MODERATE")
            rel_g_clr = ("#10B981" if profile.repeat_buyer_rate >= 0.70 else
                         "#EF4444" if profile.repeat_buyer_rate < 0.30 else "#38BDF8")
            with sc3:
                st.markdown(
                    f"""<div class='signal-card'>
                    <div class='signal-label'>Relationship Signal</div>
                    <div class='signal-score' style='color:#38BDF8'>
                        {profile.relationship_score:.1f}
                        <span class='signal-denom'>/100</span>
                    </div>
                    <div class='signal-weight'>Weight 30% &nbsp;·&nbsp; S_REL</div>
                    <div class='signal-kv'>
                        <span>Repeat Buyers</span>
                        <span class='signal-kv-val'>{profile.repeat_buyer_rate:.0%}</span>
                    </div>
                    <div class='signal-kv'>
                        <span>Unique Partners</span>
                        <span class='signal-kv-val'>{profile.unique_buyers}</span>
                    </div>
                    <div class='signal-kv'>
                        <span>Network</span>
                        <span class='sig-grade' style='color:{rel_g_clr}'>{rel_grade}</span>
                    </div>
                    </div>""",
                    unsafe_allow_html=True,
                )

        # ── Inner Tab 2: Invoicing Timeline ───────────────────────────────────
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

        # ── Inner Tab 3: Ledger SQL Logs ──────────────────────────────────────
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

    # ┌─────────────────────────────────────────────────────────────────────────
    # │  RIGHT COLUMN — Credit Underwriting Suite
    # └─────────────────────────────────────────────────────────────────────────
    with right_col:
        st.markdown(
            "<div class='section-header'>Underwriting Decision</div>",
            unsafe_allow_html=True,
        )

        # ── Scheme recommendation card ────────────────────────────────────────
        if rec_scheme:
            st.markdown(
                f"""<div class='scheme-block'>
                <div style='font-size:0.6rem;font-weight:700;letter-spacing:0.13em;
                            text-transform:uppercase;color:#34D399;margin-bottom:0.4rem'>
                    Recommended Scheme</div>
                <div style='font-size:1.05rem;font-weight:700;color:#D1FAE5;
                            margin-bottom:0.15rem'>{rec_scheme}</div>
                <div class='scheme-amount'>{fmt_inr(loan_amt)}</div>
                <div style='font-size:0.7rem;color:#6EE7B7;margin-top:0.18rem'>
                    Maximum Capital Ceiling</div>
                </div>""",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """<div style='background:rgba(239,68,68,0.07);
                              border:1px solid rgba(239,68,68,0.22);
                              border-radius:12px;padding:1.1rem 1.4rem'>
                <div style='font-size:0.88rem;color:#FCA5A5;font-weight:600'>
                    No Eligible Scheme Identified</div>
                <div style='font-size:0.75rem;color:#7F1D1D;margin-top:0.3rem'>
                    Review eligibility gaps below</div>
                </div>""",
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height:0.55rem'></div>", unsafe_allow_html=True)

        # ── Confidence meter ──────────────────────────────────────────────────
        st.markdown(
            "<div style='font-size:0.6rem;font-weight:700;letter-spacing:0.13em;"
            "text-transform:uppercase;color:#475569;margin-bottom:0.35rem'>"
            "Match Confidence</div>",
            unsafe_allow_html=True,
        )
        st.progress(confidence, text=f"{confidence:.0%}")

        # ── Underwriting inputs ───────────────────────────────────────────────
        st.markdown(
            f"""<div style='margin-top:0.6rem'>
            <div class='underwrite-kv'>
              <span class='underwrite-kv-key'>Invoices Reviewed</span>
              <span class='underwrite-kv-val'>{profile.total_invoices}</span>
            </div>
            <div class='underwrite-kv'>
              <span class='underwrite-kv-key'>Unique Trade Partners</span>
              <span class='underwrite-kv-val'>{profile.unique_buyers}</span>
            </div>
            <div class='underwrite-kv'>
              <span class='underwrite-kv-key'>Years Active</span>
              <span class='underwrite-kv-val'>{profile.years_active}</span>
            </div>
            <div class='underwrite-kv'>
              <span class='underwrite-kv-key'>Annual Turnover</span>
              <span class='underwrite-kv-val'>{fmt_inr(profile.annual_turnover)}</span>
            </div>
            <div class='underwrite-kv' style='border-bottom:none'>
              <span class='underwrite-kv-key'>Severe Default Rate</span>
              <span class='underwrite-kv-val'
                style='color:{"#EF4444" if profile.severe_default_rate > 0.15 else "#10B981"}'>
                {profile.severe_default_rate:.0%}</span>
            </div>
            </div>""",
            unsafe_allow_html=True,
        )

        # ── Alternative schemes ───────────────────────────────────────────────
        if alts:
            st.markdown(
                "<div class='section-header' style='margin-top:0.8rem'>"
                "Alternative Schemes</div>",
                unsafe_allow_html=True,
            )
            alts_html = "".join(
                f"<div class='alt-row'>· {a}</div>" for a in alts
            )
            st.markdown(alts_html, unsafe_allow_html=True)

        # ── Risk signals ──────────────────────────────────────────────────────
        st.markdown(
            "<div class='section-header' style='margin-top:0.8rem'>"
            "Risk Signals</div>",
            unsafe_allow_html=True,
        )
        if flags:
            st.markdown(
                "".join(f"<div class='flag-item'>{f}</div>" for f in flags),
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div style='font-size:0.78rem;color:#10B981'>"
                "✓ No risk signals identified</div>",
                unsafe_allow_html=True,
            )

        # ── Eligibility gaps ──────────────────────────────────────────────────
        if missing:
            st.markdown(
                "<div class='section-header' style='margin-top:0.8rem'>"
                "Eligibility Gaps</div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                "".join(f"<div class='gap-item'>{g}</div>" for g in missing),
                unsafe_allow_html=True,
            )

        # ── Raw JSON ──────────────────────────────────────────────────────────
        st.markdown("<div style='height:0.4rem'></div>", unsafe_allow_html=True)
        with st.expander("Raw Underwriting JSON"):
            st.code(json.dumps(routing, indent=2, ensure_ascii=False), language="json")


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 2 — SMART ONBOARDING (multilingual)
# ══════════════════════════════════════════════════════════════════════════════

with tab_onboard:
    st.markdown(
        "<div class='section-header' style='border-color:#1E2229'>"
        "Multilingual Trade Statement Parser — Lucknow Textile Cluster</div>",
        unsafe_allow_html=True,
    )
    st.markdown(f"## {tr['page_header']}")
    st.caption(tr["page_sub"])
    st.divider()

    # ── Sample buttons ────────────────────────────────────────────────────────
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
        st.divider()

        ob_left, ob_right = st.columns(2, gap="large")

        # ── Left card: extracted parameters ───────────────────────────────────
        with ob_left:
            _nd   = tr["not_detected"]
            _dsuf = tr["days_suffix"]

            cluster_val  = parsed.cluster or _nd
            turnover_val = fmt_inr(parsed.monthly_turnover)  if parsed.monthly_turnover     else _nd
            latency_val  = f"{parsed.payment_latency_days} {_dsuf}" if parsed.payment_latency_days else _nd
            loan_val     = fmt_inr(parsed.loan_amount)       if parsed.loan_amount           else _nd

            c_cls = "detected" if parsed.cluster              else "missing"
            t_cls = "detected" if parsed.monthly_turnover     else "missing"
            l_cls = "detected" if parsed.payment_latency_days else "missing"
            n_cls = "detected" if parsed.loan_amount          else "missing"

            st.markdown(
                f"""<div class='ob-card'>
                <div class='ob-card-title'>{tr['extracted_title']}</div>
                <div class='ob-param-row'>
                  <span class='ob-param-key'>{tr['cluster_label']}</span>
                  <span class='ob-param-val {c_cls}'>{cluster_val}</span>
                </div>
                <div class='ob-param-row'>
                  <span class='ob-param-key'>{tr['turnover_label']}</span>
                  <span class='ob-param-val {t_cls}'>{turnover_val}</span>
                </div>
                <div class='ob-param-row'>
                  <span class='ob-param-key'>{tr['latency_label']}</span>
                  <span class='ob-param-val {l_cls}'>{latency_val}</span>
                </div>
                <div class='ob-param-row'>
                  <span class='ob-param-key'>{tr['loan_req_label']}</span>
                  <span class='ob-param-val {n_cls}'>{loan_val}</span>
                </div>
                </div>""",
                unsafe_allow_html=True,
            )

            st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)
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

        # ── Right card: agent recommendation ──────────────────────────────────
        with ob_right:
            ob_lbl, ob_css, ob_clr = score_meta(synth.credit_score)
            t_band   = tr["bands"].get(ob_lbl, ob_lbl)

            ob_scheme = ob_route.get("recommended_scheme")
            ob_loan   = float(ob_route.get("max_eligible_loan_amount", 0.0))
            ob_conf   = float(ob_route.get("confidence_score", 0.0))
            ob_alts   = ob_route.get("alternative_schemes", [])
            ob_flags  = [_t_flag(f, lang) for f in ob_route.get("risk_flags", [])]
            _raw_gaps = [_t_gap(g, lang)  for g in ob_route.get("missing_parameters", [])]
            ob_gaps   = list(dict.fromkeys(_raw_gaps))
            t_scheme  = tr["schemes"].get(ob_scheme, ob_scheme) if ob_scheme else None

            flags_html = "".join(
                f"<div class='ob-flag-row'>{f}</div>" for f in ob_flags
            ) or (f"<span style='font-size:0.78rem;color:#10B981'>"
                  f"✓ {tr['none_label']}</span>")

            gaps_html = "".join(
                f"<div class='ob-gap-row'>{g}</div>" for g in ob_gaps
            )

            alts_html = "".join(
                f"<div style='font-size:0.78rem;color:#64748B;padding:0.22rem 0;"
                f"border-bottom:1px solid #1E2229'>· {tr['schemes'].get(a,a)}</div>"
                for a in ob_alts
            )

            scheme_html = (
                f"<div style='font-size:0.95rem;font-weight:700;color:#D1FAE5'>{t_scheme}</div>"
                f"<div style='font-size:1.75rem;font-weight:900;color:#10B981;line-height:1.1'>"
                f"{fmt_inr(ob_loan)}</div>"
                f"<div style='font-size:0.68rem;color:#6EE7B7;margin-top:0.1rem'>"
                f"{tr['max_loan_label']}</div>"
            ) if t_scheme else (
                f"<div style='color:#FCA5A5;font-size:0.85rem'>No eligible scheme identified</div>"
            )

            alts_section = (
                f"<div style='margin:0.5rem 0 0.2rem'>"
                f"<div style='font-size:0.6rem;font-weight:700;letter-spacing:0.12em;"
                f"text-transform:uppercase;color:#475569;margin-bottom:0.25rem'>"
                f"{tr['alt_label']}</div>{alts_html}</div>"
            ) if alts_html else ""

            gaps_section = (
                f"<div style='margin-top:0.55rem'>"
                f"<div style='font-size:0.6rem;font-weight:700;letter-spacing:0.12em;"
                f"text-transform:uppercase;color:#475569;margin-bottom:0.3rem'>"
                f"{tr['gaps_label']}</div>{gaps_html}</div>"
            ) if gaps_html else ""

            st.markdown(
                f"""<div class='ob-card'>
                <div class='ob-card-title'>{tr['rec_title']}</div>

                <div style='text-align:center;padding:0.25rem 0 0.6rem'>
                  <div class='ob-score-big' style='color:{ob_clr}'>{synth.credit_score}</div>
                  <span class='risk-badge {ob_css}'>{t_band}</span>
                </div>

                <hr style='border:none;border-top:1px solid #1E2229;margin:0.55rem 0'>

                <div style='margin-bottom:0.6rem'>
                  {scheme_html}
                </div>

                <div style='margin-bottom:0.4rem'>
                  <span style='font-size:0.72rem;color:#475569'>
                    {tr['confidence_label']}:&nbsp;</span>
                  <span style='font-size:0.85rem;font-weight:700;color:#F1F5F9'>
                    {ob_conf:.0%}</span>
                </div>

                {alts_section}

                <hr style='border:none;border-top:1px solid #1E2229;margin:0.55rem 0'>

                <div>
                  <div style='font-size:0.6rem;font-weight:700;letter-spacing:0.12em;
                              text-transform:uppercase;color:#475569;margin-bottom:0.3rem'>
                    {tr['risk_label']}</div>
                  {flags_html}
                </div>

                {gaps_section}
                </div>""",
                unsafe_allow_html=True,
            )

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
