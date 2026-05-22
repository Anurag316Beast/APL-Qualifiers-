"""
app.py
------
Streamlit dashboard for the Lucknow Artisan Alternative Credit Scoring System.

Run:      streamlit run app.py
Requires: artisan_credit.db  —  run `python3 main.py` first to generate it.
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
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────────────────────────────────────
# Global CSS
# ──────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }
    [data-testid="stMetricValue"] { font-size: 1.1rem !important; }

    .stag {
        font-size: 0.67rem; font-weight: 700; letter-spacing: 0.12em;
        text-transform: uppercase; color: #9ca3af;
        padding-bottom: 0.45rem; margin-bottom: 0.6rem;
        border-bottom: 1px solid #e5e7eb;
    }
    .rbadge {
        display: inline-block; padding: 0.28rem 0.9rem;
        border-radius: 9999px; font-size: 0.75rem;
        font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase;
    }
    .b-prime       { background: #dcfce7; color: #15803d; }
    .b-near        { background: #e0f2fe; color: #0369a1; }
    .b-sub         { background: #fef9c3; color: #b45309; }
    .b-deep        { background: #ffedd5; color: #c2410c; }
    .b-invis       { background: #fee2e2; color: #b91c1c; }

    .scheme-card {
        background: #f0fdf4; border: 1px solid #bbf7d0;
        border-radius: 0.75rem; padding: 1.25rem 1.5rem;
    }
    .sc-title { font-size: 0.67rem; font-weight: 700; letter-spacing: 0.1em;
                text-transform: uppercase; color: #6b7280; margin-bottom: 0.25rem; }
    .sc-name  { font-size: 1.3rem; font-weight: 700; color: #15803d; }
    .sc-amt   { font-size: 2rem; font-weight: 800; color: #166534; margin-top: 0.15rem; }
    .sc-sub   { font-size: 0.72rem; color: #6b7280; margin-top: 0.15rem; }

    .flag-row {
        background: #fff7ed; border-left: 3px solid #f97316;
        border-radius: 0 0.375rem 0.375rem 0;
        padding: 0.42rem 0.75rem; margin-bottom: 0.35rem;
        font-size: 0.81rem; color: #431407;
    }
    .gap-row {
        background: #fef2f2; border-left: 3px solid #ef4444;
        border-radius: 0 0.375rem 0.375rem 0;
        padding: 0.42rem 0.75rem; margin-bottom: 0.35rem;
        font-size: 0.81rem; color: #450a0a;
    }

    /* ── Onboarding page styles ─────────────────────────────────────── */
    .ob-sample-label {
        font-size: 0.72rem; font-weight: 700; letter-spacing: 0.1em;
        text-transform: uppercase; color: #9ca3af;
        margin-bottom: 0.55rem; margin-top: 0.25rem;
    }
    .ob-card {
        background: #ffffff; border: 1px solid #e5e7eb;
        border-radius: 0.85rem; padding: 1.4rem 1.6rem;
        height: 100%; box-shadow: 0 1px 4px rgba(0,0,0,0.05);
    }
    .ob-card-title {
        font-size: 0.67rem; font-weight: 700; letter-spacing: 0.11em;
        text-transform: uppercase; color: #6b7280;
        padding-bottom: 0.55rem; margin-bottom: 0.85rem;
        border-bottom: 1px solid #f3f4f6;
    }
    .ob-param-row {
        display: flex; justify-content: space-between; align-items: center;
        padding: 0.6rem 0; border-bottom: 1px solid #f9fafb;
        font-size: 0.85rem;
    }
    .ob-param-row:last-child { border-bottom: none; }
    .ob-param-key  { color: #6b7280; font-weight: 500; }
    .ob-param-val  { font-weight: 700; color: #111827; text-align: right; max-width: 55%; }
    .ob-param-val.detected { color: #15803d; }
    .ob-param-val.missing  { color: #9ca3af; font-style: italic; font-weight: 400; }
    .ob-score-big {
        font-size: 3.2rem; font-weight: 900; text-align: center;
        line-height: 1.1; margin: 0.4rem 0 0.25rem 0;
    }
    .ob-flag-row {
        background: #fff7ed; border-left: 3px solid #f97316;
        border-radius: 0 0.375rem 0.375rem 0;
        padding: 0.38rem 0.7rem; margin-bottom: 0.3rem;
        font-size: 0.79rem; color: #431407;
    }
    .ob-gap-row {
        background: #fef2f2; border-left: 3px solid #ef4444;
        border-radius: 0 0.375rem 0.375rem 0;
        padding: 0.38rem 0.7rem; margin-bottom: 0.3rem;
        font-size: 0.79rem; color: #450a0a;
    }
    .ob-processing {
        display: flex; align-items: center; gap: 0.8rem;
        background: linear-gradient(135deg,#eff6ff 0%,#f0fdf4 100%);
        border: 1px solid #bfdbfe; border-radius: 0.75rem;
        padding: 0.9rem 1.4rem; margin: 0.75rem 0;
        font-size: 0.88rem; color: #1e3a5f; font-weight: 500;
    }
    .ob-pulse {
        width: 11px; height: 11px; border-radius: 50%;
        background: #3b82f6; flex-shrink: 0;
        animation: ob-pulse-anim 1.2s ease-in-out infinite;
    }
    @keyframes ob-pulse-anim {
        0%,100% { transform: scale(1);   opacity: 1;   }
        50%      { transform: scale(1.6); opacity: 0.4; }
    }

    #MainMenu { visibility: hidden; }
    footer     { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ──────────────────────────────────────────────────────────────────────────────
# Multilingual UI strings
# ──────────────────────────────────────────────────────────────────────────────

TRANSLATIONS: dict[str, dict] = {
    "English": {
        "lang_label":        "Interface Language",
        "dashboard_tab":     "📊 Credit Dashboard",
        "onboarding_tab":    "🗣️ Smart Onboarding",
        "page_header":       "Conversational Artisan Onboarding",
        "page_sub":          "Paste or type the artisan's trade statement below — English, Hindi, or Awadhi all work.",
        "sample_label":      "Load a sample statement:",
        "btn_en":            "English",
        "btn_hi":            "Hindi (हिन्दी)",
        "btn_aw":            "Awadhi (अवधी)",
        "input_label":       "Artisan Trade Statement",
        "input_placeholder": "Describe your embroidery workshop, monthly sales, payment cycles, and loan needs…",
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
        "lang_label":        "भाषा चुनें",
        "dashboard_tab":     "📊 क्रेडिट डैशबोर्ड",
        "onboarding_tab":    "🗣️ स्मार्ट ऑनबोर्डिंग",
        "page_header":       "बातचीत आधारित कारीगर ऑनबोर्डिंग",
        "page_sub":          "नीचे कारीगर का व्यापार विवरण दर्ज करें — हिंदी, अंग्रेज़ी या अवधी में।",
        "sample_label":      "नमूना विवरण लोड करें:",
        "btn_en":            "अंग्रेज़ी",
        "btn_hi":            "हिंदी",
        "btn_aw":            "अवधी",
        "input_label":       "कारीगर का व्यापार विवरण",
        "input_placeholder": "अपने कारखाने, मासिक बिक्री, भुगतान चक्र और ऋण की ज़रूरत का विवरण दें…",
        "analyze_btn":       "विश्लेषण करें →",
        "processing":        "बहुभाषी विवरण का विश्लेषण हो रहा है…",
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
        "lang_label":        "भाषा चुनव",
        "dashboard_tab":     "📊 क्रेडिट झाँकी",
        "onboarding_tab":    "🗣️ नाव दर्ज करव",
        "page_header":       "बात-चीत से कारीगर दर्ज करव",
        "page_sub":          "नीचे कारीगर का बेपार बिबरन लिखव — हिंदी, अंगरेजी या अवधी मा।",
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
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def fmt_inr(v: float) -> str:
    if v >= 1_00_00_000: return f"₹{v/1_00_00_000:.2f} Cr"
    if v >= 1_00_000:    return f"₹{v/1_00_000:.2f} L"
    if v >= 1_000:       return f"₹{v/1_000:.1f} K"
    return f"₹{v:.0f}"


def score_meta(s: int) -> tuple[str, str, str]:
    if s >= 750: return "Prime",            "b-prime", "#16a34a"
    if s >= 650: return "Near-Prime",       "b-near",  "#0369a1"
    if s >= 550: return "Subprime",         "b-sub",   "#b45309"
    if s >= 450: return "Deep Subprime",    "b-deep",  "#c2410c"
    return               "Credit Invisible","b-invis",  "#b91c1c"


def _build_synthetic_profile(parsed: ParsedStatement) -> CreditProfile:
    """Estimate a CreditProfile from parsed trade-statement data."""
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
        flags.append(
            f"Payment latency of {latency} days detected — above 60-day threshold"
        )
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
    """Translate a synthetic risk flag into the target language."""
    if lang == "English":
        return flag
    m = re.match(
        r"Payment latency of (\d+) days detected — above 60-day threshold", flag
    )
    if m:
        n = m.group(1)
        if lang == "Hindi (हिन्दी)":
            return f"भुगतान में {n} दिन की देरी — 60-दिन की सीमा से अधिक"
        return f"{n} दिन पइसा आव मा देरी — 60-दिन सीमा से ऊपर"
    if "Low stated monthly turnover" in flag:
        if lang == "Hindi (हिन्दी)":
            return "कम मासिक कारोबार MUDRA पात्रता को सीमित कर सकता है"
        return "कम महीना कमाई MUDRA पात्रता सीमित कर सकत है"
    return flag


def _t_gap(gap: str, lang: str) -> str:
    """Translate a routing eligibility-gap string into the target language."""
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
    df = pd.read_sql(
        "SELECT id, name, cluster, craft_type, annual_turnover, artisan_card_status "
        "FROM artisans ORDER BY name",
        conn,
    )
    conn.close()
    return df


@st.cache_data
def load_profile(artisan_id: int) -> CreditProfile:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    p = score_artisan(artisan_id, conn)
    conn.close()
    return p


@st.cache_data
def load_routing(artisan_id: int) -> dict:
    return route_artisan(load_profile(artisan_id), DB_PATH)


@st.cache_data
def load_invoices(artisan_id: int) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(
        "SELECT invoice_date, buyer_name, invoice_value, tax_paid, "
        "payment_status, overdue_days "
        "FROM gst_invoices WHERE artisan_id=? ORDER BY invoice_date DESC",
        conn, params=(artisan_id,),
    )
    conn.close()
    df["invoice_date"] = pd.to_datetime(df["invoice_date"])
    return df


@st.cache_data
def load_ledger(artisan_id: int) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(
        "SELECT buyer_name, order_date, delivery_date, settlement_date, "
        "order_value, settlement_time_days, is_repeat_buyer "
        "FROM order_ledgers WHERE artisan_id=? ORDER BY order_date DESC",
        conn, params=(artisan_id,),
    )
    conn.close()
    return df


# ──────────────────────────────────────────────────────────────────────────────
# Chart builders
# ──────────────────────────────────────────────────────────────────────────────

def chart_gauge(score: int, color: str) -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number={"font": {"size": 52, "color": color, "family": "Inter,sans-serif"}},
        gauge={
            "axis": {
                "range": [300, 850],
                "tickvals": [300, 450, 550, 650, 750, 850],
                "tickfont": {"size": 9},
            },
            "bar":        {"color": color, "thickness": 0.22},
            "bgcolor":    "white",
            "borderwidth": 0,
            "steps": [
                {"range": [300, 450], "color": "#fee2e2"},
                {"range": [450, 550], "color": "#ffedd5"},
                {"range": [550, 650], "color": "#fef9c3"},
                {"range": [650, 750], "color": "#e0f2fe"},
                {"range": [750, 850], "color": "#dcfce7"},
            ],
        },
    ))
    fig.update_layout(
        height=230, margin=dict(t=15, b=0, l=15, r=15),
        paper_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter,sans-serif"},
    )
    return fig


def chart_subscores(profile: CreditProfile) -> go.Figure:
    cats   = ["Trade Relationship\n(30%)", "Invoice Fulfillment\n(40%)", "Cash Flow\nConsistency (30%)"]
    vals   = [profile.relationship_score, profile.fulfillment_score, profile.cashflow_score]
    colors = ["#059669", "#0891b2", "#6366f1"]

    fig = go.Figure(go.Bar(
        y=cats, x=vals, orientation="h",
        marker_color=colors,
        text=[f"{v:.0f}" for v in vals],
        textposition="inside", insidetextanchor="middle",
        textfont={"size": 12, "color": "white", "family": "Inter,sans-serif"},
        hovertemplate="%{y}: %{x:.1f}/100<extra></extra>",
    ))
    fig.add_vline(
        x=profile.composite_raw, line_dash="dot",
        line_color="#374151", line_width=1.5,
        annotation_text=f"  Composite {profile.composite_raw:.0f}",
        annotation_position="top right",
        annotation_font_size=9, annotation_font_color="#374151",
    )
    fig.update_layout(
        xaxis=dict(range=[0, 100], title="Score (0–100)",
                   showgrid=True, gridcolor="#f3f4f6", tickfont={"size": 9}),
        yaxis=dict(showgrid=False, tickfont={"size": 9}),
        showlegend=False,
        height=200, margin=dict(t=15, b=35, l=10, r=75),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter,sans-serif"},
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
        line=dict(color="#4f46e5", width=2.5), marker=dict(size=4),
        fill="tozeroy", fillcolor="rgba(79,70,229,0.06)",
        hovertemplate="%{x}: ₹%{y:,.0f}<extra>Actual</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=m_adj["year_month"], y=m_adj["adj_value"],
        mode="lines", name="Seasonality-Adjusted",
        line=dict(color="#94a3b8", width=1.5, dash="dot"),
        hovertemplate="%{x}: ₹%{y:,.0f}<extra>Adjusted</extra>",
    ))
    fig.update_layout(
        xaxis=dict(showgrid=False, tickangle=-45,
                   tickfont=dict(size=8), nticks=12),
        yaxis=dict(title="Revenue (₹)", showgrid=True, gridcolor="#f3f4f6",
                   tickformat=",.0f", tickfont=dict(size=9)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1, font=dict(size=9)),
        height=290, margin=dict(t=30, b=65, l=70, r=15),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter,sans-serif"},
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
    colors = ["#16a34a", "#0891b2", "#d97706", "#ea580c", "#dc2626"]

    fig = go.Figure(go.Bar(
        x=labels, y=counts, marker_color=colors,
        text=pcts, textposition="outside", textfont=dict(size=11),
        hovertemplate="%{x}<br>Count: %{y} (%{text})<extra></extra>",
    ))
    fig.update_layout(
        xaxis=dict(showgrid=False),
        yaxis=dict(title="Invoice Count", showgrid=True,
                   gridcolor="#f3f4f6", tickfont=dict(size=9)),
        height=290, margin=dict(t=30, b=20, l=55, r=20),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter,sans-serif"},
        showlegend=False,
    )
    return fig


# ──────────────────────────────────────────────────────────────────────────────
# Guard: database must exist
# ──────────────────────────────────────────────────────────────────────────────

if not os.path.exists(DB_PATH):
    st.error(
        "**Database not found.**  "
        "Run `python3 main.py` in this directory to initialise and populate it, "
        "then refresh this page."
    )
    st.stop()


# ──────────────────────────────────────────────────────────────────────────────
# Sidebar — language selector + artisan directory
# ──────────────────────────────────────────────────────────────────────────────

all_artisans = load_artisan_list()

with st.sidebar:
    # Language selector (always visible, affects onboarding tab)
    lang = st.radio(
        "Language / भाषा",
        ["English", "Hindi (हिन्दी)", "Awadhi (अवधी)"],
        horizontal=True,
        key="interface_lang",
        label_visibility="visible",
    )

    st.divider()

    # Artisan directory (used by the dashboard tab)
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

    view = view.copy()
    view["label"] = view.apply(
        lambda r: f"{r['name']}  ·  {r['cluster']}  ·  {r['craft_type']}", axis=1
    )
    chosen_label = st.selectbox("", options=view["label"].tolist(),
                                label_visibility="collapsed")

    chosen_row = view[view["label"] == chosen_label].iloc[0]
    artisan_id = int(chosen_row["id"])

    st.divider()
    st.markdown(f"**{chosen_row['name']}**")
    st.markdown(
        f"<span style='font-size:0.8rem;color:#6b7280'>"
        f"{chosen_row['cluster']} · {chosen_row['craft_type']}</span>",
        unsafe_allow_html=True,
    )
    st.metric("Annual Turnover", fmt_inr(float(chosen_row["annual_turnover"])))
    st.metric("Card Status",     chosen_row["artisan_card_status"])


# ──────────────────────────────────────────────────────────────────────────────
# Main tabs
# ──────────────────────────────────────────────────────────────────────────────

tr = TRANSLATIONS[lang]

tab_dash, tab_onboard = st.tabs([tr["dashboard_tab"], tr["onboarding_tab"]])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Credit Dashboard  (existing functionality, unchanged)
# ══════════════════════════════════════════════════════════════════════════════

with tab_dash:
    profile   = load_profile(artisan_id)
    routing   = load_routing(artisan_id)
    invoices  = load_invoices(artisan_id)
    ledger    = load_ledger(artisan_id)

    band_label, band_css, band_color = score_meta(profile.credit_score)

    # ── Page header ──────────────────────────────────────────────────────────
    st.markdown(
        "<div class='stag'>Alternative Credit Intelligence — Lucknow Textile Artisans</div>",
        unsafe_allow_html=True,
    )
    st.markdown(f"## {profile.name}")
    st.caption(
        f"{profile.craft_type} &nbsp;·&nbsp; {profile.cluster} cluster "
        f"&nbsp;·&nbsp; {profile.years_active} years active "
        f"&nbsp;·&nbsp; Card: **{profile.artisan_card_status}**"
    )
    st.divider()

    # ── Hero zone ─────────────────────────────────────────────────────────────
    h1, h2, h3 = st.columns([1, 1.3, 1.7])

    with h1:
        st.markdown("<div class='stag'>Credit Score</div>", unsafe_allow_html=True)
        st.plotly_chart(
            chart_gauge(profile.credit_score, band_color),
            use_container_width=True, config={"displayModeBar": False},
        )
        st.markdown(
            f"<div style='text-align:center'>"
            f"<span class='rbadge {band_css}'>{band_label}</span></div>",
            unsafe_allow_html=True,
        )

    with h2:
        st.markdown("<div class='stag'>Score Breakdown</div>", unsafe_allow_html=True)
        st.plotly_chart(
            chart_subscores(profile),
            use_container_width=True, config={"displayModeBar": False},
        )
        st.caption("Weights: Cash Flow 30% · Fulfillment 40% · Relationship 30%")

    with h3:
        st.markdown("<div class='stag'>Key Metrics</div>", unsafe_allow_html=True)
        ka, kb = st.columns(2)
        kc, kd = st.columns(2)
        ke, kf = st.columns(2)
        with ka: st.metric("Annual Turnover",     fmt_inr(profile.annual_turnover))
        with kb: st.metric("Avg Monthly Revenue", fmt_inr(profile.avg_monthly_revenue))
        with kc: st.metric("Fast-Payment Rate",   f"{profile.fast_payment_rate:.0%}",
                            help="Invoices settled within 45 days")
        with kd: st.metric("Severe Default Rate", f"{profile.severe_default_rate:.0%}",
                            help="Invoices overdue more than 90 days")
        with ke: st.metric("Repeat-Buyer Share",  f"{profile.repeat_buyer_rate:.0%}")
        with kf: st.metric("Revenue CV (adj)",    f"{profile.revenue_cv_adjusted:.3f}",
                            help="Seasonality-adjusted CV. Lower = more consistent.")

    st.divider()

    # ── Analytics ─────────────────────────────────────────────────────────────
    a1, a2 = st.columns(2)

    with a1:
        st.markdown("<div class='stag'>Monthly Revenue Consistency</div>", unsafe_allow_html=True)
        if not invoices.empty:
            st.plotly_chart(chart_revenue(invoices), use_container_width=True,
                            config={"displayModeBar": False})
            st.caption(
                f"Seasonality-adjusted CV: **{profile.revenue_cv_adjusted:.3f}** — "
                "dashed line strips out expected seasonal swings to isolate genuine volatility."
            )
        else:
            st.info("No invoice data available.")

    with a2:
        st.markdown("<div class='stag'>Invoice Payment Latency Distribution</div>",
                    unsafe_allow_html=True)
        if not invoices.empty:
            st.plotly_chart(chart_latency(invoices), use_container_width=True,
                            config={"displayModeBar": False})
            st.caption(
                f"{profile.total_invoices} invoices &nbsp;·&nbsp; "
                f"{profile.fast_payment_rate:.0%} within 45 days &nbsp;·&nbsp; "
                f"{profile.severe_default_rate:.0%} severe defaults (>90 days)"
            )
        else:
            st.info("No invoice data available.")

    st.divider()

    # ── Data tables ───────────────────────────────────────────────────────────
    st.markdown("<div class='stag'>Transaction Records</div>", unsafe_allow_html=True)
    tab_inv, tab_led = st.tabs(["GST Invoice History", "Digital Khata (Order Ledger)"])

    with tab_inv:
        if not invoices.empty:
            d = invoices.copy()
            d["invoice_date"]  = d["invoice_date"].dt.strftime("%d %b %Y")
            d["invoice_value"] = d["invoice_value"].apply(fmt_inr)
            d["tax_paid"]      = d["tax_paid"].apply(fmt_inr)
            d.columns = ["Date", "Buyer", "Invoice Value", "Tax Paid", "Status", "Delay (days)"]
            st.dataframe(d.head(30), use_container_width=True, hide_index=True,
                         column_config={"Delay (days)": st.column_config.NumberColumn(
                             "Delay (days)", format="%d d")})
            st.caption(f"Showing most recent 30 of {len(invoices)} invoices")
        else:
            st.info("No invoice data on record.")

    with tab_led:
        if not ledger.empty:
            d = ledger.copy()
            d["order_value"]     = d["order_value"].apply(fmt_inr)
            d["is_repeat_buyer"] = d["is_repeat_buyer"].map({1: "Yes", 0: "No"})
            d.columns = ["Buyer", "Order Date", "Delivery Date", "Settlement Date",
                         "Order Value", "Settlement (days)", "Repeat Buyer"]
            st.dataframe(d.head(30), use_container_width=True, hide_index=True,
                         column_config={"Settlement (days)": st.column_config.NumberColumn(
                             "Settlement (days)", format="%d d")})
            st.caption(f"Showing most recent 30 of {len(ledger)} entries")
        else:
            st.info("No ledger data on record.")

    st.divider()

    # ── Agent underwriting output ─────────────────────────────────────────────
    st.markdown("<div class='stag'>Agent Underwriting Decision</div>", unsafe_allow_html=True)

    rec_scheme = routing.get("recommended_scheme")
    loan_amt   = float(routing.get("max_eligible_loan_amount", 0.0))
    confidence = float(routing.get("confidence_score", 0.0))
    alts       = routing.get("alternative_schemes", [])
    flags      = routing.get("risk_flags", [])
    missing    = routing.get("missing_parameters", [])

    u1, u2, u3 = st.columns([1.2, 1.0, 1.4])

    with u1:
        if rec_scheme:
            st.markdown(
                f"<div class='scheme-card'>"
                f"<div class='sc-title'>Recommended Scheme</div>"
                f"<div class='sc-name'>{rec_scheme}</div>"
                f"<div class='sc-amt'>{fmt_inr(loan_amt)}</div>"
                f"<div class='sc-sub'>Maximum eligible loan amount</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            st.error("No eligible government scheme identified for this profile.")

    with u2:
        st.markdown("**Match Confidence**")
        st.progress(confidence, text=f"{confidence:.0%}")
        if alts:
            st.markdown("**Alternative Schemes**")
            for alt in alts:
                st.markdown(f"- {alt}")
        st.markdown("**Underwriting Inputs**")
        st.markdown(
            f"- {profile.total_invoices} GST invoices reviewed  \n"
            f"- {profile.unique_buyers} unique trade partners  \n"
            f"- {profile.years_active} years of trade history"
        )

    with u3:
        if flags:
            st.markdown("**Risk Signals**")
            for flag in flags:
                st.markdown(f"<div class='flag-row'>{flag}</div>", unsafe_allow_html=True)
        if missing:
            st.markdown("**Eligibility Gaps**")
            for gap in missing:
                st.markdown(f"<div class='gap-row'>{gap}</div>", unsafe_allow_html=True)
        if not flags and not missing:
            st.success("No risk signals or eligibility gaps identified.")

    with st.expander("Raw Underwriting JSON"):
        st.code(json.dumps(routing, indent=2, ensure_ascii=False), language="json")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Smart Onboarding (multilingual)
# ══════════════════════════════════════════════════════════════════════════════

with tab_onboard:

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown(
        "<div class='stag'>Multilingual Trade Statement Parser — Lucknow Textile Cluster</div>",
        unsafe_allow_html=True,
    )
    st.markdown(f"## {tr['page_header']}")
    st.caption(tr["page_sub"])
    st.divider()

    # ── Sample template buttons ───────────────────────────────────────────────
    st.markdown(
        f"<div class='ob-sample-label'>{tr['sample_label']}</div>",
        unsafe_allow_html=True,
    )

    sb1, sb2, sb3, _sbpad = st.columns([1.3, 1.3, 1.3, 4.1])
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
        height=165,
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

    # ── Results ───────────────────────────────────────────────────────────────
    if st.session_state.get("onboard_analyzed") and stmt and stmt.strip():

        # Animated processing card (visible while Python runs)
        _proc_slot = st.empty()
        _proc_slot.markdown(
            f"""<div class='ob-processing'>
            <div class='ob-pulse'></div>
            <span>{tr['processing']}</span>
            </div>""",
            unsafe_allow_html=True,
        )

        parsed   = parse_trade_statement(stmt)
        synth    = _build_synthetic_profile(parsed)
        ob_route = route_artisan(synth, DB_PATH)

        _proc_slot.empty()   # replace animation with results

        st.divider()

        left_col, right_col = st.columns(2, gap="large")

        # ── Left card: Extracted Trade Parameters ──────────────────────────
        with left_col:
            _nd   = tr["not_detected"]
            _dsuf = tr["days_suffix"]

            cluster_val  = parsed.cluster or _nd
            turnover_val = fmt_inr(parsed.monthly_turnover) if parsed.monthly_turnover else _nd
            latency_val  = f"{parsed.payment_latency_days} {_dsuf}" if parsed.payment_latency_days else _nd
            loan_val     = fmt_inr(parsed.loan_amount) if parsed.loan_amount else _nd

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

            # Sub-scores breakdown below the card
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(
                "<div class='stag'>Estimated Sub-Scores</div>",
                unsafe_allow_html=True,
            )
            ss1, ss2, ss3 = st.columns(3)
            with ss1:
                st.metric("Cash Flow", f"{synth.cashflow_score:.0f}/100",
                          help="Based on estimated payment latency → CV proxy")
            with ss2:
                st.metric("Fulfillment", f"{synth.fulfillment_score:.0f}/100",
                          help="Fast-payment & default rates inferred from latency")
            with ss3:
                st.metric("Relationship", f"{synth.relationship_score:.0f}/100",
                          help="Conservative estimate (assumed 5 yr tenure, 65% repeat buyers)")

        # ── Right card: Localized Agent Recommendation ──────────────────────
        with right_col:
            ob_band_lbl, ob_band_css, ob_band_clr = score_meta(synth.credit_score)
            t_band    = tr["bands"].get(ob_band_lbl, ob_band_lbl)

            ob_scheme = ob_route.get("recommended_scheme")
            ob_loan   = float(ob_route.get("max_eligible_loan_amount", 0.0))
            ob_conf   = float(ob_route.get("confidence_score", 0.0))
            ob_alts   = ob_route.get("alternative_schemes", [])
            ob_flags  = [_t_flag(f, lang) for f in ob_route.get("risk_flags", [])]
            _raw_gaps = [_t_gap(g, lang) for g in ob_route.get("missing_parameters", [])]
            ob_gaps   = list(dict.fromkeys(_raw_gaps))  # deduplicate, preserve order
            t_scheme  = tr["schemes"].get(ob_scheme, ob_scheme) if ob_scheme else None

            # Build inner HTML fragments
            flags_html = "".join(
                f"<div class='ob-flag-row'>{f}</div>" for f in ob_flags
            ) or f"<span style='font-size:0.82rem;color:#6b7280'>{tr['none_label']}</span>"

            gaps_html = "".join(
                f"<div class='ob-gap-row'>{g}</div>" for g in ob_gaps
            )

            alts_html = "".join(
                f"<div style='font-size:0.81rem;color:#374151;padding:0.12rem 0'>"
                f"· {tr['schemes'].get(a, a)}</div>"
                for a in ob_alts
            )

            if t_scheme:
                scheme_html = (
                    f"<div style='font-size:1rem;font-weight:700;color:#15803d'>{t_scheme}</div>"
                    f"<div style='font-size:1.7rem;font-weight:800;color:#166534;line-height:1.15'>"
                    f"{fmt_inr(ob_loan)}</div>"
                    f"<div style='font-size:0.72rem;color:#6b7280;margin-top:0.1rem'>"
                    f"{tr['max_loan_label']}</div>"
                )
            else:
                scheme_html = (
                    f"<div style='color:#b91c1c;font-size:0.88rem'>"
                    f"No eligible scheme identified</div>"
                )

            alts_section = (
                f"<div style='margin:0.5rem 0 0.25rem 0'>"
                f"<span style='font-size:0.72rem;color:#9ca3af;text-transform:uppercase;"
                f"letter-spacing:0.08em;font-weight:700'>{tr['alt_label']}</span>"
                f"{alts_html}</div>"
            ) if alts_html else ""

            gaps_section = (
                f"<div style='margin-top:0.5rem'>"
                f"<div style='font-size:0.72rem;font-weight:700;letter-spacing:0.08em;"
                f"text-transform:uppercase;color:#9ca3af;margin-bottom:0.35rem'>"
                f"{tr['gaps_label']}</div>"
                f"{gaps_html}</div>"
            ) if gaps_html else ""

            st.markdown(
                f"""<div class='ob-card'>
                <div class='ob-card-title'>{tr['rec_title']}</div>

                <div style='text-align:center;padding:0.3rem 0 0.6rem 0'>
                    <div class='ob-score-big' style='color:{ob_band_clr}'>{synth.credit_score}</div>
                    <span class='rbadge {ob_band_css}'>{t_band}</span>
                </div>

                <hr style='border:none;border-top:1px solid #f3f4f6;margin:0.6rem 0'>

                <div style='margin-bottom:0.65rem'>{scheme_html}</div>

                <div style='margin-bottom:0.45rem'>
                    <span style='font-size:0.75rem;color:#6b7280'>{tr['confidence_label']}: </span>
                    <span style='font-size:0.88rem;font-weight:700'>{ob_conf:.0%}</span>
                </div>

                {alts_section}

                <hr style='border:none;border-top:1px solid #f3f4f6;margin:0.65rem 0'>

                <div>
                    <div style='font-size:0.72rem;font-weight:700;letter-spacing:0.08em;
                                text-transform:uppercase;color:#9ca3af;margin-bottom:0.35rem'>
                        {tr['risk_label']}</div>
                    {flags_html}
                </div>

                {gaps_section}
                </div>""",
                unsafe_allow_html=True,
            )

        # Raw JSON expander
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("Raw Parser + Router JSON"):
            combined = {
                "parsed_statement": {
                    "cluster":              parsed.cluster,
                    "monthly_turnover":     parsed.monthly_turnover,
                    "payment_latency_days": parsed.payment_latency_days,
                    "loan_amount":          parsed.loan_amount,
                },
                "synthetic_credit_profile": {
                    "credit_score":      synth.credit_score,
                    "cashflow_score":    synth.cashflow_score,
                    "fulfillment_score": synth.fulfillment_score,
                    "relationship_score": synth.relationship_score,
                    "annual_turnover":   synth.annual_turnover,
                },
                "routing_output": ob_route,
            }
            st.code(json.dumps(combined, indent=2, ensure_ascii=False), language="json")
