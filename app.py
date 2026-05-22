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
import sqlite3

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from artisan_credit.agent_router import route_artisan
from artisan_credit.data_generator import MONTHLY_SEASONALITY
from artisan_credit.scoring_engine import CreditProfile, score_artisan

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

    #MainMenu { visibility: hidden; }
    footer     { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def fmt_inr(v: float) -> str:
    if v >= 1_00_00_000: return f"₹{v/1_00_00_000:.2f} Cr"
    if v >= 1_00_000:    return f"₹{v/1_00_000:.2f} L"
    if v >= 1_000:       return f"₹{v/1_000:.1f} K"
    return f"₹{v:.0f}"


def score_meta(s: int) -> tuple[str, str, str]:
    if s >= 750: return "Prime",           "b-prime", "#16a34a"
    if s >= 650: return "Near-Prime",      "b-near",  "#0369a1"
    if s >= 550: return "Subprime",        "b-sub",   "#b45309"
    if s >= 450: return "Deep Subprime",   "b-deep",  "#c2410c"
    return               "Credit Invisible","b-invis", "#b91c1c"


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
# Sidebar — artisan selector
# ──────────────────────────────────────────────────────────────────────────────

all_artisans = load_artisan_list()

with st.sidebar:
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
# Load data for selected artisan
# ──────────────────────────────────────────────────────────────────────────────

profile   = load_profile(artisan_id)
routing   = load_routing(artisan_id)
invoices  = load_invoices(artisan_id)
ledger    = load_ledger(artisan_id)

band_label, band_css, band_color = score_meta(profile.credit_score)


# ──────────────────────────────────────────────────────────────────────────────
# Page header
# ──────────────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────────────
# HERO ZONE
# ──────────────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────────────
# ANALYTICS
# ──────────────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────────────
# DATA TABLES
# ──────────────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────────────
# AGENT UNDERWRITING OUTPUT
# ──────────────────────────────────────────────────────────────────────────────

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
