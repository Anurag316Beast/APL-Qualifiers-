# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the full pipeline (drops DB, regenerates data, scores all artisans, prints Markdown report)
python3 main.py

# Launch the Streamlit dashboard (requires artisan_credit.db — run main.py first)
streamlit run app.py

# Re-generate the database only
python3 data_generator.py

# Run a specific module in isolation (example: score artisan id=1)
python3 -c "
import sqlite3
from scoring_engine import score_artisan
conn = sqlite3.connect('artisan_credit.db')
print(score_artisan(1, conn))
conn.close()
"

# Inspect the live database
sqlite3 artisan_credit.db ".tables"
sqlite3 artisan_credit.db "SELECT name, annual_turnover FROM artisans LIMIT 5;"
```

No build step, no test runner, no linter configured yet. Dependencies are stdlib + `pandas` + `numpy` + `streamlit` + `plotly`.

```bash
# Test the multilingual parser against all three sample texts
python3 -c "
from language_parser import parse_trade_statement
texts = [
  'I run an embroidery workshop in Chowk. Monthly sales around 45,000 rupees. Exporters clear bills after 60 days. Need a loan of 80,000.',
  'चौक में चिकनकारी का काम है। महीने का 35,000 रुपये का इनवॉइस बनता है पर पेमेंट दो महीने बाद मिलती है। 1 लाख का लोन चाहिए।',
  'भइया, हम अमिनाबाद मा जरदोजी कै काम करीथिन। महीनवा मा करीब 40,000 रुपिया आवत है पै दुई महीना बाद पइसा देवत हैं। 50,000 रुपिया चाही।',
]
for t in texts:
    p = parse_trade_statement(t)
    print(p.cluster, p.monthly_turnover, p.payment_latency_days, p.loan_amount)
"
```

## Architecture

The pipeline is strictly linear with no circular imports:

```
data_generator.py  ──exports──▶  MONTHLY_SEASONALITY (dict)
       │                                  │
       │  populate_database()             │  (imported for de-trending)
       ▼                                  ▼
   artisan_credit.db  ◀──────  scoring_engine.py
                                   │  score_artisan() → CreditProfile
                                   ▼
                              agent_router.py
                                   │  route_artisan() → dict (JSON-serialisable)
                                   ▼
                 ┌─────────────────┴──────────────────┐
                 │                                    │
            main.py                               app.py
    (orchestration + Markdown report)    (Streamlit dashboard — two tabs:
                                          Credit Dashboard + Smart Onboarding)
                                                       ▲
                                          language_parser.py
                                          (free-text → ParsedStatement →
                                           synthetic CreditProfile)
```

**`app.py`** is the Streamlit entry-point. It imports from the `artisan_credit/` package (a mirror of the three core modules) rather than the top-level files, avoiding import-path issues when Streamlit changes the working directory. It uses `@st.cache_data` keyed on `artisan_id` so artisan switches are instant after first load. It has two tabs: `📊 Credit Dashboard` (existing analytics) and `🗣️ Smart Onboarding` (multilingual free-text onboarding).

**`language_parser.py`** is a standalone regex + keyword parser. Given a free-form trade statement in English, Hindi, or Awadhi, it returns a `ParsedStatement` dataclass with `cluster`, `monthly_turnover`, `payment_latency_days`, and `loan_amount`. It is imported only by `app.py` and has no dependencies beyond stdlib `re`. The `_build_synthetic_profile()` function in `app.py` converts a `ParsedStatement` into a `CreditProfile` (using a latency-bucket lookup table) so the onboarding path can call the real `route_artisan()` against the live DB.

**`data_generator.py`** owns all synthetic data logic and the `MONTHLY_SEASONALITY` constant. It is the sole writer to the DB (via `pandas.DataFrame.to_sql`). The payer archetype (`good` / `average` / `struggling`) is deterministically derived from the artisan index so scores are reproducible without storing the archetype in the DB.

**`scoring_engine.py`** is read-only against the DB. It imports `MONTHLY_SEASONALITY` from `data_generator` to ensure the seasonal de-trending uses the same multipliers that were used during generation. The `CreditProfile` dataclass is the shared DTO passed between the scoring engine and the router.

**`agent_router.py`** is also read-only. It queries `govt_schemes` at call time (no in-memory caching), so adding or modifying a scheme row is immediately reflected without touching Python code. The two-step logic — hard gates first, then confidence ranking — keeps eligibility rules in SQL and ranking logic in Python.

**`schema.sql`** is the single source of truth for the relational model. `data_generator.populate_database()` reads and executes it via `conn.executescript()`, so schema changes only need to happen in one place.

## Key domain constants

| Constant | Location | Purpose |
|----------|----------|---------|
| `MONTHLY_SEASONALITY` | `data_generator.py` | Revenue multipliers by calendar month; shared with scoring engine for de-trending |
| `RNG_SEED = 42` | `data_generator.py` | Makes all synthetic data deterministic |
| Score formula weights | `scoring_engine.py` docstring | 30% cash-flow, 40% fulfillment, 30% relationship → mapped to 300–850 |
| Confidence weights | `agent_router.py` docstring | 0.40 credit headroom + 0.35 bracket centrality + 0.25 card status |

## Extending the project

**Add a new government scheme:** Insert a row into `govt_schemes` in `data_generator._seed_govt_schemes()`. No router code changes needed.

**Wrap an API:** `score_artisan(artisan_id, conn)` and `route_artisan(profile, db_path)` are already decoupled from I/O — expose them directly as handler functions.

**Add a new scoring signal:** Add a column to the relevant table in `schema.sql`, populate it in `data_generator.py`, then incorporate it into one of the three `_*_score()` helper functions in `scoring_engine.py`. Keep the composite weights summing to 1.0 and the raw sub-scores in the 0–100 range.

**Add a new onboarding language:** Add an entry to `TRANSLATIONS` in `app.py` (all UI strings), add a key to `SAMPLES` (demo text), and extend the keyword lists in `language_parser.py` (`_CLUSTER_PATTERNS`, `_TURNOVER_RULES`, `_LATENCY_*_RULES`, `_LOAN_RULES`).

**Add a new extractable field:** Add regex rules to `language_parser.py`, add the field to `ParsedStatement`, and consume it in `_build_synthetic_profile()` in `app.py`. Render it in the left onboarding card.
