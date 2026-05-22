# Artisan Credit Intelligence — Lucknow

An alternative credit scoring engine for bank-invisible textile artisans (Chikankari / Zardozi) in Lucknow's Chowk and Aminabad clusters. The system builds a credit profile from GST invoice history, informal order ledgers, and buyer-relationship data, then automatically maps each artisan to eligible government loan schemes (MUDRA, PM Vishwakarma, ODOP).

---

## Problem

Over 250,000 textile artisans in Lucknow are effectively locked out of formal credit. They lack the collateral and CIBIL history that banks require, yet many run consistent, seasonal businesses with reliable trade relationships. This system surfaces that hidden creditworthiness.

## Solution

A three-stage pipeline:

```
Alternative Data  →  Credit Score (300–850)  →  Scheme Eligibility Router
```

1. **Scoring engine** computes a composite alternative credit score from:
   - Cash flow consistency (30%) — seasonality-adjusted revenue CV
   - Invoice fulfillment (40%) — prompt payment rate vs. severe defaults
   - Trade relationship depth (30%) — repeat-buyer share + tenure

2. **Agent router** cross-references the score against live government scheme rules in SQLite and outputs a ranked eligibility recommendation with confidence scores.

3. **Streamlit dashboard** presents the full profile, charts, and underwriting decision to a loan officer or demo judge.

---

## Project Structure

```
APL-Qualifiers-/
├── artisan_credit/          # Core package
│   ├── __init__.py
│   ├── schema.sql           # Database DDL
│   ├── data_generator.py    # Synthetic data + DB seeding
│   ├── scoring_engine.py    # Credit scoring logic + CreditProfile dataclass
│   └── agent_router.py      # Scheme eligibility routing
├── app.py                   # Streamlit dashboard entry point
├── main.py                  # CLI pipeline entry point
├── requirements.txt
├── setup_env.sh             # One-shot bootstrap script
└── .python-version          # Python 3.12.6
```

---

## Quickstart

### Option A — Bootstrap script (recommended)

```bash
chmod +x setup_env.sh
./setup_env.sh
```

This creates a `.venv`, installs dependencies, seeds the database, and opens the dashboard automatically.

### Option B — Manual setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python3 main.py            # seed DB + print CLI report
streamlit run app.py       # launch dashboard at http://localhost:8501
```

---

## Running Commands

| Command | Purpose |
|---------|---------|
| `python3 main.py` | Regenerate DB and print full Markdown report to stdout |
| `streamlit run app.py` | Launch interactive dashboard |
| `python3 -m artisan_credit.data_generator` | Seed DB only |

---

## Scoring Formula

```
S_composite = 0.30 × S_cashflow + 0.40 × S_fulfillment + 0.30 × S_relationship

Credit Score = 300 + (S_composite / 100) × 550
```

| Component | Weight | Method |
|-----------|--------|--------|
| Cash Flow Consistency | 30% | Exponential decay on seasonality-adjusted CV: `100 × exp(−1.5 × CV_adj)` |
| Invoice Fulfillment | 40% | `100 × (fast_rate − 2 × default_rate)` where fast = paid ≤45d, default = overdue >90d |
| Trade Relationship | 30% | `70 × repeat_buyer_rate + min(30, years_active × 2)` |

## Government Schemes

| Scheme | Loan Range | Key Criteria |
|--------|-----------|--------------|
| MUDRA Shishu | ₹10K – ₹50K | Turnover up to ₹5L, score ≥ 300 |
| MUDRA Kishor | ₹50K – ₹5L | Turnover ₹1L–₹25L, score ≥ 450 |
| MUDRA Tarun | ₹5L – ₹10L | Turnover ≥ ₹10L, score ≥ 580 |
| PM Vishwakarma | ₹10K – ₹2L | Artisan card (Active/Pending), score ≥ 400 |
| ODOP Credit Line | ₹1L – ₹10L | Turnover ₹5L–₹50L, Chikankari/Zardozi craft, score ≥ 520 |

---

## Tech Stack

- **Python 3.12** · **Pandas** · **NumPy** — data pipeline and scoring math
- **SQLite** — artisan profiles, transactions, and scheme rules
- **Streamlit** + **Plotly** — interactive dashboard
- No external APIs or ML models — all scoring is deterministic and explainable

---

## Sample Output

```
Population Credit Score Summary
Mean: 686  |  Range: 501–790  |  50/50 artisans matched to a scheme

Score Band Distribution
Prime (750+)        →  12 artisans (24%)
Near-Prime (650–749)→  25 artisans (50%)
Subprime (550–649)  →   6 artisans (12%)
Deep Subprime       →   7 artisans (14%)
```
