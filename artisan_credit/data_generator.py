"""
data_generator.py
-----------------
Synthesises realistic transactional data for 50 mock textile artisans
across the Chowk and Aminabad clusters of Lucknow.

Seasonal revenue multipliers per calendar month encode:
  - Festive spikes: Oct-Nov (Diwali + wedding season), Jan (winter weddings),
    Apr (spring/Eid embroidery demand)
  - Monsoon lulls: Jul-Aug — outdoor drying of hand-embroidered fabric is
    blocked by humidity, slowing Chikankari production significantly
  - Moderate shoulder months: Feb-Mar, May-Jun, Sep, Dec

These constants are exported and imported by scoring_engine.py for
seasonality-adjusted CV computation. Both modules must use the same table
so that the de-trending is internally consistent.
"""

import os
import random
import sqlite3
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd

RNG_SEED: int = 42
np.random.seed(RNG_SEED)
random.seed(RNG_SEED)

# Month → revenue multiplier relative to a flat baseline of 1.0.
MONTHLY_SEASONALITY: dict[int, float] = {
    1:  1.35,   # Jan: winter wedding commissions
    2:  0.90,   # Feb: post-season lull
    3:  0.95,   # Mar: moderate
    4:  1.20,   # Apr: spring weddings / Eid orders
    5:  0.85,   # May: summer slump
    6:  0.80,   # Jun: pre-monsoon slowdown
    7:  0.55,   # Jul: monsoon lull — outdoor drying blocked
    8:  0.60,   # Aug: monsoon continues
    9:  0.95,   # Sep: post-monsoon recovery
    10: 1.45,   # Oct: Diwali festive peak
    11: 1.50,   # Nov: wedding + festive overlap
    12: 1.10,   # Dec: winter wedding season
}

ARTISAN_NAMES: list[str] = [
    "Razia Begum",      "Sabra Khatoon",    "Mehjabeen Ansari", "Farida Bano",
    "Nusrat Fatima",    "Rukhsana Parveen", "Nasreen Sultana",  "Zubeda Khanam",
    "Shaista Begum",    "Rehana Bano",      "Amna Siddiqui",    "Bilquis Ansari",
    "Hajra Khatoon",    "Ishrat Fatima",    "Jahanara Begum",   "Kaneez Fatima",
    "Lubna Ansari",     "Mumtaz Khatoon",   "Naina Begum",      "Ozma Parveen",
    "Parveen Bano",     "Qurrat Ansari",    "Rashida Khatoon",  "Sana Fatima",
    "Tahira Begum",     "Umme Salma",       "Varsha Begum",     "Wajida Khatoon",
    "Yasmin Ansari",    "Zohra Bano",       "Asghari Khanam",   "Bano Fatima",
    "Chandni Parveen",  "Dilnoza Begum",    "Eram Khatoon",     "Farhana Ansari",
    "Gulnaz Khatoon",   "Hina Fatima",      "Irum Begum",       "Jabeen Khatoon",
    "Kalsum Ansari",    "Laila Begum",      "Mahbuba Khatoon",  "Nazmeen Fatima",
    "Oliya Begum",      "Parwana Khatoon",  "Qamar Fatima",     "Rubina Ansari",
    "Saleha Khatoon",   "Tabassum Begum",
]

# First 10 buyers are primarily Chowk-based; last 10 are Aminabad-facing exporters.
BUYER_NAMES: list[str] = [
    "Lucknow Chikankari House",  "Hazratganj Emporium",     "UP Handloom Corp",
    "Nawabi Textiles",           "Zari Bazaar Traders",     "Raza & Sons Fabrics",
    "Chowk Wholesale Market",    "Awadh Emporium",          "Rang Mahal Fabrics",
    "Dastkar Cooperative",       "Craftroot Exports",        "Gulmohar Exports",
    "Heritage Fabric Store",     "Banarasi Palace",          "Aminabad Traders",
    "Sangam Textiles",           "Kiran Fabrics",            "Mehfil Boutique",
    "Aaina Exports",             "Shehnai Garments",
]


def _artisan_card_number(idx: int, status: str) -> Optional[str]:
    if status == "Unregistered":
        return None
    return f"UP-LKO-{2021 + (idx % 3)}-{str(idx + 1001).zfill(5)}"


def _payer_profile(artisan_idx: int) -> str:
    """
    Deterministic payment behaviour archetype derived from artisan index.
    Returns one of: 'good' (40%), 'average' (40%), 'struggling' (20%).
    Determinism ensures reproducible scores across module re-runs.
    """
    bucket = (artisan_idx * 7 + 13) % 10
    if bucket < 4:
        return "good"
    elif bucket < 8:
        return "average"
    return "struggling"


def generate_artisans(n: int = 50) -> pd.DataFrame:
    """Return a DataFrame of n artisan base profiles (no DB IDs yet)."""
    rng = np.random.default_rng(RNG_SEED)

    clusters = rng.choice(["Chowk", "Aminabad"], size=n, p=[0.42, 0.58])

    craft_types: list[str] = []
    for cluster in clusters:
        p = [0.75, 0.25] if cluster == "Chowk" else [0.50, 0.50]
        craft_types.append(rng.choice(["Chikankari", "Zardozi"], p=p))

    card_statuses = rng.choice(["Active", "Pending", "Unregistered"], size=n, p=[0.48, 0.30, 0.22])
    card_numbers = [_artisan_card_number(i, card_statuses[i]) for i in range(n)]
    years_active = rng.integers(3, 28, size=n)

    turnovers: list[float] = []
    for ct in craft_types:
        if ct == "Chikankari":
            turnovers.append(float(rng.uniform(150_000, 1_200_000)))
        else:
            turnovers.append(float(rng.uniform(200_000, 1_800_000)))

    records = [
        {
            "name":                ARTISAN_NAMES[i],
            "cluster":             clusters[i],
            "craft_type":          craft_types[i],
            "artisan_card_number": card_numbers[i],
            "artisan_card_status": card_statuses[i],
            "phone":               f"9{rng.integers(100_000_000, 999_999_999)}",
            "years_active":        int(years_active[i]),
            "annual_turnover":     round(turnovers[i], 2),
        }
        for i in range(n)
    ]
    return pd.DataFrame(records)


def generate_gst_invoices(artisans_df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate 24 months (Jan 2023 – Dec 2024) of GST invoices.

    Each artisan produces 1-4 invoices per month; monsoon months get one fewer.
    Seasonal multipliers scale invoice values so that monthly revenue tracks
    MONTHLY_SEASONALITY closely, allowing the scoring engine to de-trend accurately.

    Payment delays are drawn from archetype-specific discrete distributions:
      good:      [0, 15, 30, 45, 60]  days  — mostly within terms
      average:   [0, 30, 45, 60, 90, 120]   — mix of on-time and delayed
      struggling:[0, 30, 60, 90, 120, 150]  — frequent delays, material defaults
    """
    rng = np.random.default_rng(RNG_SEED + 1)
    records: list[dict] = []
    invoice_counter = 1

    delay_params: dict[str, tuple[list[int], list[float]]] = {
        "good":      ([0, 15, 30, 45, 60],        [0.50, 0.25, 0.15, 0.07, 0.03]),
        "average":   ([0, 30, 45, 60, 90, 120],   [0.30, 0.25, 0.20, 0.15, 0.07, 0.03]),
        "struggling":([0, 30, 60, 90, 120, 150],  [0.15, 0.20, 0.25, 0.20, 0.12, 0.08]),
    }

    for _, artisan in artisans_df.iterrows():
        artisan_id = int(artisan["id"])
        monthly_base = float(artisan["annual_turnover"]) / 12.0
        profile = _payer_profile(artisan_id - 1)
        delay_vals, delay_probs = delay_params[profile]

        # Buyers drawn from the cluster-appropriate half of BUYER_NAMES
        buyer_pool = BUYER_NAMES[:10] if artisan["cluster"] == "Chowk" else BUYER_NAMES[10:]

        for year in (2023, 2024):
            for month in range(1, 13):
                sf = MONTHLY_SEASONALITY[month]
                n_inv = int(rng.choice([1, 2, 3, 4], p=[0.20, 0.40, 0.30, 0.10]))
                if sf < 0.70:
                    n_inv = max(1, n_inv - 1)

                for _ in range(n_inv):
                    day = int(rng.integers(1, 28))
                    inv_date = date(year, month, day)
                    noise = float(rng.uniform(0.75, 1.25))
                    inv_value = round(monthly_base * sf / n_inv * noise, 2)
                    tax = round(inv_value * 0.05, 2)  # 5% GST on handicrafts

                    buyer = buyer_pool[int(rng.integers(0, len(buyer_pool)))]
                    delay = int(rng.choice(delay_vals, p=delay_probs))

                    if delay == 0:
                        status = "Paid"
                    elif delay <= 60:
                        status = "Pending"
                    else:
                        status = "Overdue"

                    records.append({
                        "artisan_id":     artisan_id,
                        "invoice_number": f"INV-{artisan_id:03d}-{invoice_counter:05d}",
                        "invoice_date":   inv_date.isoformat(),
                        "buyer_name":     buyer,
                        "invoice_value":  inv_value,
                        "tax_paid":       tax,
                        "payment_status": status,
                        "overdue_days":   delay,
                    })
                    invoice_counter += 1

    return pd.DataFrame(records)


def generate_order_ledgers(artisans_df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate informal order ledger entries capturing buyer relationships,
    delivery timelines, and settlement speeds outside the formal GST trail.

    Each artisan is assigned a stable pool of buyers.  The first (n-2) buyers
    in that pool are flagged as repeat buyers — a trust signal used by the
    scoring engine.  Settlement times follow the same payer archetypes as GST.
    """
    rng = np.random.default_rng(RNG_SEED + 2)
    records: list[dict] = []
    start = date(2023, 1, 1)
    date_range = (date(2024, 12, 31) - start).days

    settle_bounds: dict[str, tuple[int, int]] = {
        "good":       (5,  40),
        "average":    (10, 75),
        "struggling": (20, 120),
    }

    for _, artisan in artisans_df.iterrows():
        artisan_id = int(artisan["id"])
        profile = _payer_profile(artisan_id - 1)
        low, high = settle_bounds[profile]

        n_buyers = int(rng.integers(3, 8))
        buyer_pool = list(rng.choice(BUYER_NAMES, size=min(n_buyers, len(BUYER_NAMES)), replace=False))
        repeat_set = set(buyer_pool[:max(1, len(buyer_pool) - 2)])

        n_orders = int(rng.integers(18, 37))
        turnover = float(artisan["annual_turnover"])

        for _ in range(n_orders):
            offset = int(rng.integers(0, date_range))
            order_date = start + timedelta(days=offset)
            delivery_days = int(rng.integers(7, 46))
            delivery_date = order_date + timedelta(days=delivery_days)
            settle_days = int(rng.integers(low, high + 1))
            settlement_date = delivery_date + timedelta(days=settle_days)

            buyer = buyer_pool[int(rng.integers(0, len(buyer_pool)))]
            order_value = round(turnover / n_orders * float(rng.uniform(0.6, 1.4)), 2)

            records.append({
                "artisan_id":          artisan_id,
                "buyer_name":          buyer,
                "order_date":          order_date.isoformat(),
                "delivery_date":       delivery_date.isoformat(),
                "settlement_date":     settlement_date.isoformat(),
                "order_value":         order_value,
                "settlement_time_days": settle_days,
                "is_repeat_buyer":     1 if buyer in repeat_set else 0,
            })

    return pd.DataFrame(records).sort_values("artisan_id").reset_index(drop=True)


def _seed_govt_schemes(conn: sqlite3.Connection) -> None:
    """Insert canonical government scheme eligibility parameters."""
    schemes = [
        {
            "scheme_name":          "MUDRA Shishu",
            "scheme_category":      "MUDRA",
            "min_annual_turnover":  0.0,
            "max_annual_turnover":  500_000.0,
            "min_loan_amount":      10_000.0,
            "max_loan_amount":      50_000.0,
            "requires_artisan_card": 0,
            "min_years_active":     0,
            "min_credit_score":     300,
            "description":          "Collateral-free micro loans for nano/early-stage enterprises.",
            "eligibility_notes":    "Annual turnover up to ₹5L. No GST registration mandatory.",
        },
        {
            "scheme_name":          "MUDRA Kishor",
            "scheme_category":      "MUDRA",
            "min_annual_turnover":  100_000.0,
            "max_annual_turnover":  2_500_000.0,
            "min_loan_amount":      50_001.0,
            "max_loan_amount":      500_000.0,
            "requires_artisan_card": 0,
            "min_years_active":     1,
            "min_credit_score":     450,
            "description":          "Growth-stage MSME financing for established micro-enterprises.",
            "eligibility_notes":    "Turnover ₹1L–₹25L. Proof of existing business activity required.",
        },
        {
            "scheme_name":          "MUDRA Tarun",
            "scheme_category":      "MUDRA",
            "min_annual_turnover":  1_000_000.0,
            "max_annual_turnover":  None,
            "min_loan_amount":      500_001.0,
            "max_loan_amount":      1_000_000.0,
            "requires_artisan_card": 0,
            "min_years_active":     3,
            "min_credit_score":     580,
            "description":          "Scale-up financing for micro-enterprises with demonstrated revenue.",
            "eligibility_notes":    "Turnover above ₹10L. Bank statements or GST returns as proof.",
        },
        {
            "scheme_name":          "PM Vishwakarma",
            "scheme_category":      "PM Vishwakarma",
            "min_annual_turnover":  0.0,
            "max_annual_turnover":  5_000_000.0,
            "min_loan_amount":      10_000.0,
            "max_loan_amount":      200_000.0,
            "requires_artisan_card": 1,
            "min_years_active":     1,
            "min_credit_score":     400,
            "description":          "Collateral-free credit for traditional craftsmen with Vishwakarma card.",
            "eligibility_notes":    "Active or Pending artisan card mandatory. Phase 1: ₹1L; Phase 2: ₹2L.",
        },
        {
            "scheme_name":          "ODOP Credit Line",
            "scheme_category":      "ODOP",
            "min_annual_turnover":  500_000.0,
            "max_annual_turnover":  5_000_000.0,
            "min_loan_amount":      100_000.0,
            "max_loan_amount":      1_000_000.0,
            "requires_artisan_card": 0,
            "min_years_active":     2,
            "min_credit_score":     520,
            "description":          "One District One Product credit line for Lucknow Chikankari/Zardozi artisans.",
            "eligibility_notes":    "Craft must be Chikankari or Zardozi. Artisan card preferred but not mandatory.",
        },
    ]

    conn.executemany(
        """
        INSERT OR IGNORE INTO govt_schemes (
            scheme_name, scheme_category, min_annual_turnover, max_annual_turnover,
            min_loan_amount, max_loan_amount, requires_artisan_card, min_years_active,
            min_credit_score, description, eligibility_notes
        ) VALUES (
            :scheme_name, :scheme_category, :min_annual_turnover, :max_annual_turnover,
            :min_loan_amount, :max_loan_amount, :requires_artisan_card, :min_years_active,
            :min_credit_score, :description, :eligibility_notes
        )
        """,
        schemes,
    )
    conn.commit()


def populate_database(db_path: str = "artisan_credit.db") -> None:
    """
    Initialise schema, generate synthetic data for 50 artisans, and persist to SQLite.
    Safe to call on a fresh database only; main.py removes any existing file first.
    """
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    with open(schema_path, "r") as fh:
        conn.executescript(fh.read())

    artisans_df = generate_artisans(50)
    artisans_df.to_sql("artisans", conn, if_exists="append", index=False)

    # Re-read so that SQLite-assigned IDs are available for FK columns.
    artisans_df = pd.read_sql("SELECT * FROM artisans ORDER BY id", conn)

    invoices_df = generate_gst_invoices(artisans_df)
    invoices_df.to_sql("gst_invoices", conn, if_exists="append", index=False)

    ledger_df = generate_order_ledgers(artisans_df)
    ledger_df.to_sql("order_ledgers", conn, if_exists="append", index=False)

    _seed_govt_schemes(conn)
    conn.close()

    print(
        f"Database ready: {len(artisans_df)} artisans | "
        f"{len(invoices_df)} GST invoices | "
        f"{len(ledger_df)} ledger entries"
    )


if __name__ == "__main__":
    populate_database()
