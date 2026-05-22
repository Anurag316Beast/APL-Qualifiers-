"""
scoring_engine.py
-----------------
Alternative credit scoring engine for bank-invisible Lucknow textile artisans.

Score range: 300 (subprime) – 850 (prime), matching CIBIL conventions so that
downstream tools and loan officers work with familiar reference points.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCORING FORMULA — weighted composite on a 0–100 raw scale
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  S_composite = 0.30 × S_cashflow + 0.40 × S_fulfillment + 0.30 × S_relationship

  Final score = 300 + (S_composite / 100) × 550

────────────────────────────────────────────────────────────────
1. Cash Flow Score  S_cashflow  (weight 0.30, range 0–100)
────────────────────────────────────────────────────────────────
Goal: measure revenue consistency after removing *expected* seasonal swings,
      isolating genuine instability from the artisan's business cycle.

Method:
  a) Tag each invoice with its calendar month and divide its value by
     MONTHLY_SEASONALITY[month] → seasonality-adjusted invoice value.
  b) Aggregate to monthly totals → time series of adjusted revenues.
  c) Compute seasonality-adjusted coefficient of variation:
       CV_adj = std(monthly_adj_revenues, ddof=1) / mean(monthly_adj_revenues)
     A perfect artisan with zero idiosyncratic volatility has CV_adj ≈ 0.
  d) Apply exponential decay:
       S_cashflow = 100 × exp(−1.5 × CV_adj)
     This non-linear mapping penalises moderate volatility modestly but
     punishes extreme instability severely, appropriate for lenders.

────────────────────────────────────────────────────────────────
2. Invoice Fulfillment Score  S_fulfillment  (weight 0.40, range 0–100)
────────────────────────────────────────────────────────────────
Goal: capture payment reliability as lenders observe it — fast settlement
      and absence of serious defaults.

  fast_rate    = count(overdue_days ≤ 45) / total_invoices
  default_rate = count(overdue_days > 90) / total_invoices

  S_fulfillment = clip(100 × (fast_rate − 2 × default_rate), 0, 100)

The 2× multiplier on severe defaults reflects their outsized credit risk
signal: a single >90-day default is a stronger negative than a missed
prompt-payment opportunity.

────────────────────────────────────────────────────────────────
3. Trade Relationship Score  S_relationship  (weight 0.30, range 0–100)
────────────────────────────────────────────────────────────────
Goal: quantify commercial network depth and tenure — proxies for reputation
      capital that formal lenders cannot observe from bank statements.

  repeat_rate    = count(is_repeat_buyer = 1) / total_order_ledger_entries
  tenure_bonus   = min(30, years_active × 2)       (hard-capped at 30 pts)

  S_relationship = clip(70 × repeat_rate + tenure_bonus, 0, 100)
"""

import sqlite3
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from data_generator import MONTHLY_SEASONALITY


@dataclass
class CreditProfile:
    """Fully computed credit profile for a single artisan."""

    # --- identity ---
    artisan_id:          int
    name:                str
    cluster:             str
    craft_type:          str
    artisan_card_status: str
    years_active:        int
    annual_turnover:     float

    # --- composite score ---
    credit_score:    int   = 0
    composite_raw:   float = 0.0

    # --- sub-scores (0–100) ---
    cashflow_score:     float = 0.0
    fulfillment_score:  float = 0.0
    relationship_score: float = 0.0

    # --- supporting metrics (consumed by agent_router) ---
    avg_monthly_revenue:  float = 0.0
    revenue_cv_adjusted:  float = 0.0
    fast_payment_rate:    float = 0.0
    severe_default_rate:  float = 0.0
    repeat_buyer_rate:    float = 0.0
    total_invoices:       int   = 0
    unique_buyers:        int   = 0

    # --- qualitative risk signals ---
    risk_flags: list[str] = field(default_factory=list)


def _cashflow_score(
    invoices: pd.DataFrame,
) -> tuple[float, float, float]:
    """
    Returns (S_cashflow, avg_monthly_revenue_raw, cv_adjusted).
    See module docstring §1 for the full derivation.
    """
    if invoices.empty:
        return 0.0, 0.0, 1.0

    df = invoices.copy()
    df["invoice_date"] = pd.to_datetime(df["invoice_date"])
    df["month_num"] = df["invoice_date"].dt.month
    df["year_month"] = df["invoice_date"].dt.to_period("M")
    df["season_factor"] = df["month_num"].map(MONTHLY_SEASONALITY)
    df["adj_value"] = df["invoice_value"] / df["season_factor"]

    monthly_adj = df.groupby("year_month")["adj_value"].sum()
    monthly_raw = df.groupby("year_month")["invoice_value"].sum()

    if len(monthly_adj) < 2:
        return 50.0, float(monthly_raw.mean()), 0.5

    mean_adj = float(monthly_adj.mean())
    std_adj  = float(monthly_adj.std(ddof=1))
    cv_adj   = std_adj / mean_adj if mean_adj > 0.0 else 1.0

    s_cf     = float(np.clip(100.0 * np.exp(-1.5 * cv_adj), 0.0, 100.0))
    avg_raw  = float(monthly_raw.mean())

    return s_cf, avg_raw, cv_adj


def _fulfillment_score(
    invoices: pd.DataFrame,
) -> tuple[float, float, float, int]:
    """
    Returns (S_fulfillment, fast_payment_rate, severe_default_rate, total_invoices).
    See module docstring §2 for the full derivation.
    """
    total = len(invoices)
    if total == 0:
        return 0.0, 0.0, 0.0, 0

    fast    = int((invoices["overdue_days"] <= 45).sum())
    severe  = int((invoices["overdue_days"] > 90).sum())

    fast_rate    = fast   / total
    default_rate = severe / total

    s_ff = float(np.clip(100.0 * (fast_rate - 2.0 * default_rate), 0.0, 100.0))
    return s_ff, float(fast_rate), float(default_rate), total


def _relationship_score(
    ledger: pd.DataFrame,
    years_active: int,
) -> tuple[float, float, int]:
    """
    Returns (S_relationship, repeat_buyer_rate, unique_buyers_count).
    See module docstring §3 for the full derivation.
    """
    if ledger.empty:
        return 0.0, 0.0, 0

    total        = len(ledger)
    repeat_count = int(ledger["is_repeat_buyer"].sum())
    repeat_rate  = repeat_count / total
    unique_buyers = int(ledger["buyer_name"].nunique())

    tenure_bonus = min(30.0, years_active * 2.0)
    s_rel = float(np.clip(70.0 * repeat_rate + tenure_bonus, 0.0, 100.0))

    return s_rel, float(repeat_rate), unique_buyers


def _risk_flags(
    cv_adj:       float,
    fast_rate:    float,
    default_rate: float,
    repeat_rate:  float,
    card_status:  str,
    total_inv:    int,
) -> list[str]:
    """Produce qualitative risk signals surfaced in the agent router output."""
    flags: list[str] = []

    if total_inv < 12:
        flags.append("Thin credit file: fewer than 12 invoices on record")
    if cv_adj > 0.8:
        flags.append(f"High revenue volatility (CV_adj={cv_adj:.2f}) beyond seasonal norm")
    if default_rate > 0.15:
        flags.append(
            f"Elevated severe default rate: {default_rate:.0%} of invoices overdue > 90 days"
        )
    if fast_rate < 0.40:
        flags.append(
            f"Low prompt-payment rate: only {fast_rate:.0%} of invoices cleared within 45 days"
        )
    if repeat_rate < 0.25:
        flags.append(
            f"Weak buyer network: only {repeat_rate:.0%} repeat-buyer share in order ledger"
        )
    if card_status == "Unregistered":
        flags.append(
            "Not enrolled in PM Vishwakarma programme — limits eligibility for artisan-specific credit lines"
        )

    return flags


def score_artisan(artisan_id: int, conn: sqlite3.Connection) -> CreditProfile:
    """
    Compute a complete CreditProfile for the artisan identified by artisan_id.
    Raises IndexError if artisan_id does not exist in the database.
    """
    artisan_rows = pd.read_sql(
        "SELECT * FROM artisans WHERE id = ?", conn, params=(artisan_id,)
    )
    if artisan_rows.empty:
        raise IndexError(f"Artisan id={artisan_id} not found in database")
    artisan = artisan_rows.iloc[0]

    invoices = pd.read_sql(
        "SELECT * FROM gst_invoices WHERE artisan_id = ?", conn, params=(artisan_id,)
    )
    ledger = pd.read_sql(
        "SELECT * FROM order_ledgers WHERE artisan_id = ?", conn, params=(artisan_id,)
    )

    s_cf,  avg_rev,      cv_adj       = _cashflow_score(invoices)
    s_ff,  fast_rate,    default_rate, total_inv = _fulfillment_score(invoices)
    s_rel, repeat_rate,  unique_buyers = _relationship_score(ledger, int(artisan["years_active"]))

    composite    = 0.30 * s_cf + 0.40 * s_ff + 0.30 * s_rel
    credit_score = int(round(300.0 + (composite / 100.0) * 550.0))

    flags = _risk_flags(
        cv_adj, fast_rate, default_rate, repeat_rate,
        str(artisan["artisan_card_status"]), total_inv,
    )

    return CreditProfile(
        artisan_id           = artisan_id,
        name                 = str(artisan["name"]),
        cluster              = str(artisan["cluster"]),
        craft_type           = str(artisan["craft_type"]),
        artisan_card_status  = str(artisan["artisan_card_status"]),
        years_active         = int(artisan["years_active"]),
        annual_turnover      = float(artisan["annual_turnover"]),
        credit_score         = credit_score,
        composite_raw        = round(composite, 2),
        cashflow_score       = round(s_cf, 2),
        fulfillment_score    = round(s_ff, 2),
        relationship_score   = round(s_rel, 2),
        avg_monthly_revenue  = round(avg_rev, 2),
        revenue_cv_adjusted  = round(cv_adj, 4),
        fast_payment_rate    = round(fast_rate, 4),
        severe_default_rate  = round(default_rate, 4),
        repeat_buyer_rate    = round(repeat_rate, 4),
        total_invoices       = total_inv,
        unique_buyers        = unique_buyers,
        risk_flags           = flags,
    )


def score_all_artisans(db_path: str = "artisan_credit.db") -> list[CreditProfile]:
    """Score every artisan in the database and return profiles sorted by credit score desc."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    artisan_ids: list[int] = (
        pd.read_sql("SELECT id FROM artisans ORDER BY id", conn)["id"].tolist()
    )
    profiles = [score_artisan(int(aid), conn) for aid in artisan_ids]
    conn.close()

    return sorted(profiles, key=lambda p: p.credit_score, reverse=True)
