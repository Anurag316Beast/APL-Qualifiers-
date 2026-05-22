# SESSIONS.md

Development log for the Lucknow Artisan Credit Scoring System.

---

## Session 1 — 2026-05-22

**Goal:** Bootstrap the full backend architecture from scratch.

### Built
- `schema.sql` — 4-table relational schema (`artisans`, `gst_invoices`, `order_ledgers`, `govt_schemes`) with FK constraints and covering indices.
- `data_generator.py` — Synthetic data for 50 artisans across Chowk and Aminabad; 24 months of GST invoices with seasonal multipliers (Jul–Aug monsoon dip, Oct–Nov festive spike); informal order ledger with repeat-buyer tagging; 5 government scheme seed rows.
- `scoring_engine.py` — `CreditProfile` dataclass; 300–850 composite score (30% cash-flow CV, 40% invoice fulfillment, 30% trade relationship).
- `agent_router.py` — Hard-gate eligibility filter against live DB scheme rows; confidence-ranked JSON recommendation output.
- `main.py` — Full pipeline: DB init → data population → score all 50 → 5 archetype cards → scheme coverage table; Markdown to stdout.
- `CLAUDE.md` — Repo guidance for future Claude Code sessions.

### Key decisions
- `MONTHLY_SEASONALITY` lives in `data_generator.py` and is imported by `scoring_engine.py` so both modules de-trend against the same multipliers.
- Payer archetype (`good` / `average` / `struggling`) is derived deterministically from artisan index — no archetype column in the DB, scores are reproducible by re-running.
- `govt_schemes` rows are the sole source of eligibility rules; the router has no hardcoded scheme logic, so adding a scheme is a data change not a code change.

### Verified output (live run)
| Metric | Value |
|--------|-------|
| Artisans scored | 50 |
| GST invoices generated | 2,605 |
| Order ledger entries | 1,417 |
| Mean credit score | 686 |
| Score range | 501 – 790 |
| Artisans matched to a scheme | 50 / 50 |

### Scheme coverage
| Scheme | Count |
|--------|-------|
| MUDRA Kishor | 34 |
| MUDRA Shishu | 14 |
| PM Vishwakarma | 2 |

### Next steps
- [x] Build Streamlit dashboard (Session 2)
- [ ] Add `pytest` test suite for scoring math and router hard-gate logic.
- [ ] Expose `score_artisan` + `route_artisan` via a lightweight FastAPI layer.
- [ ] Explore adding a bureau-pull simulation (CIBIL stub) as a fourth scoring input.
- [ ] Investigate ODOP Credit Line low match rate (0 matches) — likely a turnover-floor vs. cohort-distribution mismatch.

---

## Session 2 — 2026-05-22

**Goal:** Add a production-quality Streamlit dashboard over the existing backend.

### Built
- `app.py` — Full Streamlit UI (`streamlit run app.py`). Imports cleanly from `scoring_engine`, `agent_router`, and `data_generator` with zero changes to core logic.

### UI zones
| Zone | Contents |
|------|----------|
| Sidebar | Searchable artisan selector with name/cluster/craft filter; quick-stats panel |
| Hero | Plotly gauge (300–850) with colour-coded risk band badge; horizontal sub-score bars with composite marker; 6 key metric cards |
| Analytics | Monthly revenue line chart (actual + seasonality-adjusted overlay); invoice payment latency bar chart (5 buckets, colour-coded by severity) |
| Data tables | Tabbed view: GST Invoice History + Digital Khata (Order Ledger), most recent 30 rows |
| Underwriting | Scheme recommendation card (name + max loan amount); match confidence progress bar; alternative schemes; risk-signal and eligibility-gap callouts; raw JSON expander |

### Key decisions
- All data loading uses `@st.cache_data` keyed on `artisan_id` — switching artisans is instant after first load.
- `MONTHLY_SEASONALITY` imported directly into `app.py` for the revenue de-trending chart so the displayed adjusted line matches exactly what the scoring engine computed.
- Plotly charts configured with `displayModeBar: False` to keep the interface clean for demo use.

### Verified
- `_stcore/health` returns `ok` on `localhost:8501`.
- No import errors; syntax verified before launch.

---

## Session 3 — 2026-05-22

**Goal:** Publish the project to GitHub and produce a comprehensive README for hackathon judges.

### Done
- **Initial GitHub push** — all 18 files committed and pushed to `https://github.com/Anurag316Beast/APL-Qualifiers-` (first commit on `main`).
- **README.md overhaul** — complete rewrite replacing the placeholder README with a judge-ready document covering:
  - Project title and MSME credit-invisibility hook
  - Problem vs. solution table (traditional signal → alternative proxy mapping)
  - Full ASCII architecture diagram tracing data from raw streams → SQLite → scoring modules → router → Streamlit dashboard, with row counts at each layer
  - All three sub-score formulas documented with LaTeX-style notation ($CV_{adj}$, exponential decay, fulfillment clip, relationship tenure-bonus)
  - Agent router confidence formula (three-component: credit headroom + bracket centrality + card status)
  - Government scheme eligibility table (5 schemes, min scores, loan ranges, card requirements)
  - Annotated file directory tree with one-line operational descriptions per module
  - Six-step quickstart (venv → install → `python3 main.py` → `streamlit run app.py` → REPL → raw SQLite)
  - Design decisions section explaining key architectural choices

### Commits pushed
| SHA | Message |
|-----|---------|
| `1577f61` | Initial commit: artisan credit scoring pipeline (18 files) |
| `dddde31` | docs: overhaul README with full architecture, scoring math, and quickstart |
| `735c278` | docs: update hackathon year to 2026 in README footer |

### Next steps
- [ ] Add `pytest` test suite for scoring math and router hard-gate logic.
- [ ] Expose `score_artisan` + `route_artisan` via a lightweight FastAPI layer.
- [ ] Explore adding a bureau-pull simulation (CIBIL stub) as a fourth scoring input.
- [ ] Investigate ODOP Credit Line low match rate — likely a turnover-floor vs. cohort-distribution mismatch.

---
