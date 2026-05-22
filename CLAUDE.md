# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the full pipeline (drops DB, regenerates data, scores all artisans, prints Markdown report)
python3 main.py

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
sqlite3 artisan_credit.db "SELECT name, credit_score FROM artisans LIMIT 5;"
```

No build step, no test runner, no linter configured yet. Dependencies are stdlib + `pandas` + `numpy`.

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
                               main.py  (orchestration + Markdown report)
```

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
