# Alternative Credit Scoring Engine for Credit-Invisible MSMEs
### Supply-Chain & Operational Data Pipelines for Lucknow's Artisan Clusters

> **APL Qualifiers Hackathon Submission** — Formal credit infrastructure fails India's 7 crore unorganised MSME workers. This system engineers alternative risk proxies from GST invoice trails, digital Khata ledgers, and buyer-network data to produce a CIBIL-scale credit score and route each artisan to their optimal government loan scheme — without a single bank statement.

---

## Team Alpha Coders

| Member Name | Role & Responsibility | GitHub Profile |
| :--- | :--- | :--- |
| **Radhika Pal** | Core Systems & Data Pipeline Engineer (Pandas/NumPy) | [Radhikaa2808](https://github.com/Radhikaa2808) |
| **Suyash Verma** | Interface Architect & UI Overhaul Specialist (Streamlit/CSS) | [suyashverma0](https://github.com/suyashverma0) |
| **Prakash Srivastava** | Linguistic Agent Logic & Integration Specialist (Language Parser/Auth) | [prakarsh-create](https://github.com/prakarsh-create) |
| **Anurag Chaudhary** | Lead Underwriting Domain Architect & Documentation (Financial Schemes/PDF) | [Anurag316Beast](https://github.com/Anurag316Beast) |

---

## Table of Contents

1. [The Problem & Our Solution](#the-problem--our-solution)
2. [Architecture & Data Flow](#architecture--data-flow)
3. [The Scoring Math Explained](#the-scoring-math-explained)
4. [Agent Eligibility Router](#agent-eligibility-router)
5. [File Directory Structure](#file-directory-structure)
6. [Quick Start Guide](#quick-start-guide)
7. [Design Decisions](#design-decisions)

---

## The Problem & Our Solution

### The Problem

India's Chikankari and Zardozi artisan clusters in Lucknow represent a centuries-old ₹10,000 crore handcraft industry — yet the vast majority of its 2.5 lakh artisans are **structurally invisible to formal credit markets**. Traditional underwriting models require:

- Salaried payslips or ITR filings
- Collateral (property, gold)
- Minimum 2-year CIBIL history from a scheduled bank

Artisans have none of these. Their income is seasonal, informal, and cash-heavy. A master Chikankari embroiderer with 20 years of trade relationships and a spotless payment record with Lucknow's top textile houses will receive the same rejection as a first-day defaulter — because both have a **CIBIL score of zero**.

The result: they borrow from local moneylenders at 36–60% annual interest, funding the same craft that luxury brands sell abroad at 300× markup.

### Our Solution

We replace the missing CIBIL signal with **three alternative risk proxies** that are already embedded in how artisans actually do business:

| Traditional Signal | Our Alternative Proxy |
|---|---|
| Bank account turnover | GST invoice history — 24 months of B2B transactions |
| Loan repayment history | Invoice payment latency — days-to-settlement distribution |
| Employment stability | Buyer network depth — repeat-buyer share from digital Khata |

These signals are aggregated through a **weighted composite scoring model** that outputs a score on the 300–850 CIBIL scale, making it directly legible to loan officers and NBFCs. An agentic eligibility router then maps each score to the optimal government scheme (MUDRA / PM Vishwakarma / ODOP), computing a match-confidence score and surfacing hard eligibility gaps.

---

## Architecture & Data Flow

The pipeline is strictly linear with no circular imports. Each layer has a single responsibility.

```
┌─────────────────────────────────────────────────────────────────────┐
│                     ALTERNATIVE DATA STREAMS                        │
│                                                                     │
│  ┌─────────────────┐  ┌──────────────────┐  ┌───────────────────┐  │
│  │  GST Invoices   │  │  Digital Khata   │  │  Artisan Registry │  │
│  │  (B2B invoice   │  │  (Order Ledger   │  │  (PM Vishwakarma  │  │
│  │   trail, 24mo)  │  │   + buyer IDs)   │  │   card, cluster)  │  │
│  └────────┬────────┘  └────────┬─────────┘  └────────┬──────────┘  │
└───────────┼────────────────────┼─────────────────────┼─────────────┘
            │                   │                      │
            ▼                   ▼                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│              data_generator.py  →  schema.sql                       │
│                                                                     │
│   SQLite Relational Storage  (artisan_credit.db)                    │
│   ┌──────────────┐  ┌────────────────┐  ┌──────────────────────┐   │
│   │   artisans   │  │  gst_invoices  │  │    order_ledgers     │   │
│   │  (50 rows)   │  │  (~3,600 rows) │  │    (~1,400 rows)     │   │
│   └──────────────┘  └────────────────┘  └──────────────────────┘   │
│                                         ┌──────────────────────┐   │
│                                         │    govt_schemes      │   │
│                                         │      (5 rows)        │   │
│                                         └──────────────────────┘   │
└───────────────────────────────┬─────────────────────────────────────┘
                                │  read-only SQL queries
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       scoring_engine.py                             │
│                                                                     │
│   Pandas / NumPy Scoring Modules                                    │
│                                                                     │
│   ┌──────────────────┐  ┌──────────────────┐  ┌────────────────┐   │
│   │ _cashflow_score  │  │_fulfillment_score│  │_relationship   │   │
│   │                  │  │                  │  │  _score        │   │
│   │ CV-adjusted      │  │ fast_rate &      │  │ repeat_rate &  │   │
│   │ revenue variance │  │ default_rate     │  │ tenure_bonus   │   │
│   │  → S_cashflow    │  │ → S_fulfillment  │  │ → S_relship    │   │
│   └────────┬─────────┘  └────────┬─────────┘  └───────┬────────┘   │
│            └───────────30%───────┴────40%──────────30%─┘           │
│                                  │                                  │
│              S_composite = weighted average (0–100)                 │
│              Credit Score = 300 + (S_composite / 100) × 550        │
│                                  │                                  │
│                        CreditProfile  dataclass                     │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │  CreditProfile object
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       agent_router.py                               │
│                                                                     │
│   Step 1: Fetch govt_schemes ordered by max_loan_amount DESC        │
│   Step 2: Hard-gate check per scheme (score / turnover / card)      │
│   Step 3: Confidence scoring — credit headroom + bracket            │
│            centrality + card status                                 │
│   Step 4: Rank passing schemes → best recommendation + alternatives │
│                                                                     │
│   Output: JSON { recommended_scheme, max_eligible_loan_amount,      │
│                  confidence_score, alternative_schemes,             │
│                  missing_parameters, risk_flags }                   │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           app.py                                    │
│                                                                     │
│   Streamlit Dashboard  (4 tabs for Bank Underwriter role)           │
│                                                                     │
│   📊 Credit Dashboard                                               │
│   • Credit score gauge (300–850, CIBIL-scale colour bands)          │
│   • Sub-score breakdown bar chart + 3 signal-decomposition cards    │
│   • Monthly revenue consistency plot (actual vs seasonality-adj)    │
│   • Invoice payment latency distribution (5 buckets)                │
│   • Scheme recommendation card + confidence meter + audit export    │
│   • GST invoice table + Digital Khata ledger (most recent 30 rows)  │
│                                                                     │
│   🗣️ Smart Onboarding                                               │
│   • Multilingual free-text parser (English / Hindi / Awadhi)        │
│   • Instant credit estimate + scheme recommendation                 │
│                                                                     │
│   💬 WhatsApp Business Simulation Sandbox          ← NEW            │
│   • Smartphone-styled WhatsApp chat UI                              │
│   • Simulated OCR ingest of Khata bills & dispatch notes            │
│   • Real-time SQLite write + cache bust → live dashboard update     │
│   • Full audit trail of every WhatsApp ingest event                 │
│                                                                     │
│   🔒 Audit Logs  (Bank Underwriter only)                            │
│   • Append-only event log: score views, parses, kit exports,        │
│     WhatsApp ingests                                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## The Scoring Math Explained

All sub-scores operate on a **0–100 raw scale** and are combined into a single composite that is then mapped onto the 300–850 CIBIL range.

### Composite Score & Final Mapping

```
S_composite  =  0.30 × S_cashflow  +  0.40 × S_fulfillment  +  0.30 × S_relationship

Credit Score  =  300  +  (S_composite / 100) × 550
```

The 300–850 range is chosen deliberately to match CIBIL conventions so loan officers work with reference points they already know.

---

### 1. Cash Flow Score — `S_cashflow` (weight: 30%)

**Goal:** Measure revenue *consistency* after stripping out predictable seasonal swings (monsoon lulls in July–August, Diwali peaks in October–November), isolating genuine business-cycle instability.

**Step 1 — Seasonal de-trending.** Each invoice value is divided by the corresponding month's seasonality multiplier to produce a seasonality-adjusted value:

```
adj_value  =  invoice_value / MONTHLY_SEASONALITY[month]
```

| Month | Multiplier | Season |
|---|---|---|
| Oct | 1.45 | Diwali festive peak |
| Nov | 1.50 | Wedding + festive overlap |
| Jul | 0.55 | Monsoon lull — outdoor drying blocked |
| Aug | 0.60 | Monsoon continues |

**Step 2 — Coefficient of Variation.** Monthly adjusted revenues are aggregated and their CV is computed:

$$CV_{adj} = \frac{\sigma(\text{monthly\_adj\_revenues})}{\mu(\text{monthly\_adj\_revenues})}$$

A perfect, consistent artisan has $CV_{adj} \approx 0$. The score applies **exponential decay** that penalises moderate volatility modestly but punishes severe instability harshly — appropriate for lender risk models:

$$S_{cashflow} = 100 \times e^{-1.5 \times CV_{adj}}$$

> **Interpretation:** $CV_{adj} = 0$ → $S_{cashflow} = 100$. $CV_{adj} = 0.5$ → $S_{cashflow} \approx 47$. $CV_{adj} \geq 1.5$ → $S_{cashflow} < 10$.

---

### 2. Invoice Fulfillment Score — `S_fulfillment` (weight: 40%)

**Goal:** Capture payment reliability from the GST invoice trail — the closest analogue to a loan repayment history for artisans without bank accounts.

$$\text{fast\_rate} = \frac{\text{count}(\text{overdue\_days} \leq 45)}{\text{total\_invoices}}$$

$$\text{default\_rate} = \frac{\text{count}(\text{overdue\_days} > 90)}{\text{total\_invoices}}$$

$$S_{fulfillment} = \text{clip}\Big(100 \times \big(\text{fast\_rate} - 2 \times \text{default\_rate}\big),\ 0,\ 100\Big)$$

The `2×` multiplier on severe defaults reflects their disproportionate credit-risk signal: one >90-day default is a stronger negative indicator than a single missed prompt-payment window. `clip` ensures the score never goes negative regardless of a catastrophic default cluster.

**Score thresholds used in risk flagging:**

| Condition | Flag Triggered |
|---|---|
| `fast_rate < 40%` | Low prompt-payment rate warning |
| `default_rate > 15%` | Elevated severe default rate warning |
| `total_invoices < 12` | Thin credit file warning |

---

### 3. Trade Relationship Score — `S_relationship` (weight: 30%)

**Goal:** Quantify commercial network depth and business tenure — reputation capital that is invisible to formal lenders but is the primary signal used by local trade financiers.

$$\text{repeat\_rate} = \frac{\text{count}(\text{is\_repeat\_buyer} = 1)}{\text{total\_order\_ledger\_entries}}$$

$$\text{tenure\_bonus} = \min(30,\ \text{years\_active} \times 2)$$

$$S_{relationship} = \text{clip}\Big(70 \times \text{repeat\_rate} + \text{tenure\_bonus},\ 0,\ 100\Big)$$

An artisan with 100% repeat buyers and 15+ years of trade history achieves the maximum score of 100. The tenure bonus saturates at 15 years, preventing decades-old but commercially dormant artisans from scoring artificially high.

---

## Agent Eligibility Router

Once a `CreditProfile` is computed, the router maps it to one of five government schemes using a **two-step decision process** executed in Python against live SQLite data.

### Government Schemes Supported

| Scheme | Max Loan | Min Score | Turnover Range | Artisan Card |
|---|---|---|---|---|
| MUDRA Shishu | ₹50,000 | 300 | Up to ₹5L | Not required |
| MUDRA Kishor | ₹5,00,000 | 450 | ₹1L – ₹25L | Not required |
| MUDRA Tarun | ₹10,00,000 | 580 | ₹10L+ | Not required |
| PM Vishwakarma | ₹2,00,000 | 400 | Up to ₹50L | **Required** |
| ODOP Credit Line | ₹10,00,000 | 520 | ₹5L – ₹50L | Preferred |

### Confidence Score Formula

For every scheme that passes all hard gates, a match-confidence score $C \in [0, 1]$ is computed across three weighted components:

**Credit headroom component (max 0.40):**

$$C_{credit} = 0.40 \times \frac{\text{credit\_score} - \text{min\_score}}{850 - \text{min\_score}}$$

**Turnover bracket centrality component (max 0.35):**

$$\text{position} = \frac{\text{annual\_turnover} - \text{min\_turnover}}{\text{max\_turnover} - \text{min\_turnover}}$$

$$C_{turnover} = 0.35 \times \Big(1 - |\text{position} - 0.5| \times 2\Big)$$

The centrality term penalises artisans at the extremes of a scheme's turnover band — an artisan right at the minimum threshold is a higher rejection risk than one at the centre.

**Artisan card component (max 0.25):**

$$C_{card} = \begin{cases} 0.25 & \text{if card status is Active} \\ 0.15 & \text{if card status is Pending} \\ 0.05 & \text{otherwise} \end{cases}$$

$$C = C_{credit} + C_{turnover} + C_{card}$$

The highest-confidence passing scheme becomes the primary recommendation; all others are surfaced as alternatives.

---

## File Directory Structure

```
APL-Qualifiers-/
│
├── schema.sql              # Single source of truth for the relational model.
│                           # Defines artisans, gst_invoices, order_ledgers,
│                           # govt_schemes tables + 4 performance indices.
│
├── data_generator.py       # Synthesises 50 artisan profiles + 24 months of GST
│                           # invoices + Digital Khata ledger entries. Exports
│                           # MONTHLY_SEASONALITY for use by the scoring engine.
│
├── scoring_engine.py       # Read-only scoring module. Implements the three
│                           # sub-score formulas + composite weighting + CIBIL
│                           # mapping. Produces CreditProfile dataclass objects.
│
├── agent_router.py         # Agentic eligibility router. Queries govt_schemes
│                           # at runtime (no in-memory cache), runs hard-gate
│                           # checks, computes confidence scores, returns JSON.
│
├── app.py                  # Streamlit dashboard. Four tabs: Credit Dashboard
│                           # (gauges, charts, underwriting suite), Smart
│                           # Onboarding (multilingual parser), WhatsApp
│                           # Business Simulation Sandbox (OCR ingest → live
│                           # DB write), and Audit Logs. Auth-gated by role.
│
├── main.py                 # CLI orchestration entry-point. Drops + rebuilds DB,
│                           # scores all 50 artisans, prints a full Markdown
│                           # cohort report with representative profile cards.
│
├── artisan_credit/         # Package mirror of the three core modules, used by
│   ├── __init__.py         # app.py imports (separates CLI vs. web-app paths).
│   ├── data_generator.py
│   ├── scoring_engine.py
│   ├── agent_router.py
│   └── schema.sql
│
├── requirements.txt        # Python dependencies (pandas, numpy, streamlit, plotly)
├── setup_env.sh            # Optional: one-shot environment bootstrap script
└── .python-version         # Pins Python 3.12
```

---

## Quick Start Guide

### Prerequisites

- Python 3.11+
- `git` (to clone the repository)

### 1. Clone the Repository

```bash
git clone https://github.com/Anurag316Beast/APL-Qualifiers-.git
cd APL-Qualifiers-
```

### 2. Create a Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows PowerShell
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

The core runtime dependencies are:

| Package | Purpose |
|---|---|
| `pandas` | DataFrame operations for invoice and ledger data |
| `numpy` | Vectorised scoring math (exp decay, clip, std) |
| `streamlit` | Interactive web dashboard |
| `plotly` | Gauge charts, bar charts, revenue time-series |

### 4. Initialise the Database & Run the CLI Report

This single command drops any existing database, generates 50 artisan profiles with 24 months of synthetic transaction history, scores every artisan, and prints a full Markdown cohort report to stdout:

```bash
python3 main.py
```

Expected output (truncated):

```
# Lucknow Artisan Credit Scoring System
> Initialising database at `artisan_credit.db`
Database ready: 50 artisans | 3612 GST invoices | 1400 ledger entries

## Population Credit Score Summary
| Metric                | Value |
|-----------------------|-------|
| Total artisans scored | 50    |
| Mean credit score     | 591   |
| Highest score         | 812   |
| Lowest score          | 318   |

## Scheme Coverage — Full Cohort
| Scheme           | Artisans matched |
|------------------|-----------------|
| MUDRA Kishor     | 18              |
| ODOP Credit Line | 14              |
| MUDRA Tarun      | 9               |
| PM Vishwakarma   | 6               |
| MUDRA Shishu     | 3               |
```

### 5. Launch the Interactive Dashboard

```bash
streamlit run app.py
```

Open **http://localhost:8501** in your browser and sign in using one of the two demo accounts:

| Role | Username | Password | Access Level |
| :--- | :--- | :--- | :--- |
| **Bank Underwriter** | `manager` | `password123` | Full access — Credit Dashboard, Smart Onboarding, **💬 WhatsApp Sandbox**, Audit Logs |
| **NGO Facilitator** | `assistant` | `password123` | Restricted — Smart Onboarding + **💬 WhatsApp Sandbox** |

The sidebar lets you filter artisans by cluster (Chowk / Aminabad) or search by name. Each artisan's page shows:

- Live credit score gauge (300–850 with CIBIL band colouring)
- Sub-score breakdown with composite overlay
- 24-month revenue consistency chart (actual vs. seasonality-adjusted)
- Invoice payment latency distribution (0–15d / 16–30d / 31–45d / 46–90d / 91+d)
- Scheme recommendation card with confidence meter and eligibility gaps
- Full GST invoice table and Digital Khata ledger (most recent 30 entries)

Switch to the **💬 WhatsApp Sandbox** tab to simulate a live WhatsApp Business ingest:

1. Pick any artisan from the dropdown.
2. Select a sample scanned document (Khata bill or dispatch note).
3. Click **🚀 Simulate OCR Ingest →** — the system runs the Vision → Language Parser → Credit Engine pipeline, writes a real invoice row to `gst_invoices`, and busts the dashboard cache.
4. Return to **📊 Credit Dashboard**, select the same artisan — the invoice count and recalculated credit score are updated immediately.

### 6. Score a Single Artisan via the REPL

```bash
python3 -c "
import sqlite3
from scoring_engine import score_artisan
from agent_router import route_artisan

conn = sqlite3.connect('artisan_credit.db')
profile = score_artisan(1, conn)
conn.close()

print(f'Score:        {profile.credit_score}')
print(f'Cash Flow:    {profile.cashflow_score:.1f} / 100')
print(f'Fulfillment:  {profile.fulfillment_score:.1f} / 100')
print(f'Relationship: {profile.relationship_score:.1f} / 100')

routing = route_artisan(profile)
print(f'Scheme:     {routing[\"recommended_scheme\"]}')
print(f'Max Loan:   ₹{routing[\"max_eligible_loan_amount\"]:,.0f}')
print(f'Confidence: {routing[\"confidence_score\"]:.0%}')
"
```

### 7. Inspect the Database Directly

```bash
# List all tables
sqlite3 artisan_credit.db ".tables"

# Artisan profiles
sqlite3 artisan_credit.db "
  SELECT name, cluster, craft_type, annual_turnover, artisan_card_status
  FROM artisans LIMIT 10;
"

# Invoice payment distribution
sqlite3 artisan_credit.db "
  SELECT payment_status, COUNT(*) as count
  FROM gst_invoices GROUP BY payment_status;
"

# Scheme eligibility parameters
sqlite3 artisan_credit.db "
  SELECT scheme_name, min_credit_score, max_loan_amount
  FROM govt_schemes ORDER BY max_loan_amount DESC;
"
```

---

## Design Decisions

**Why SQLite?** Zero-infrastructure, single-file, fully reproducible. The entire dataset is generated deterministically from `RNG_SEED = 42` — every `python3 main.py` produces byte-identical scores.

**Why exponential decay for cash flow, not linear?** Linear penalisation treats a $CV$ of 0.8 and 1.6 as proportionally equivalent. In practice, extreme revenue volatility is a non-linear risk signal — lenders need to see that being twice as volatile is far more than twice as risky.

**Why separate `artisan_credit/` package?** `main.py` (CLI) and `app.py` (Streamlit) both need the three core modules. The package structure avoids import-path fragility when Streamlit runs from a different working directory.

**Why no in-memory scheme caching in the router?** Adding or modifying a government scheme requires only an `INSERT` into `govt_schemes` — no Python code changes. The router re-queries at call time, keeping eligibility rules entirely in SQL and ranking logic entirely in Python.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Data pipeline & scoring | Python 3.12 · Pandas · NumPy |
| Relational storage | SQLite (zero-infrastructure, file-based) |
| Dashboard | Streamlit · Plotly |
| Scoring methodology | Deterministic, explainable — no black-box ML |

---

*Built for the APL Qualifiers Hackathon — Lucknow, 2026*
