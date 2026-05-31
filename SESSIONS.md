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

## Session 4 — 2026-05-22

**Goal:** Add a fully interactive, multilingual unstructured-data onboarding interface to the Streamlit dashboard — no external translation API.

### Built

**`language_parser.py`** (new module)
- Regex + localized keyword parser for English, Hindi (हिन्दी), and Awadhi (अवधी) trade statements.
- Extracts four structured fields from free-form dialect text:
  - `cluster` — keyword lookup (`chowk` / `चौक`, `aminabad` / `अमिनाबाद`)
  - `monthly_turnover` — number near monthly/महीने-का/महीनवा-मा-करीब patterns
  - `payment_latency_days` — direct day patterns + month-word conversion (`दो`/`दुई` महीने → 60 days)
  - `loan_amount` — loan-intent patterns + लाख expansion (1 लाख = ₹1,00,000)
- Zero external dependencies; all three built-in sample texts parse correctly.

**`app.py`** (extended)
- Language selector radio (`English` / `Hindi (हिन्दी)` / `Awadhi (अवधी)`) added to sidebar.
- Dashboard content moved into a `📊 Credit Dashboard` tab; new `🗣️ Smart Onboarding` tab added.
- Onboarding tab features:
  - Three one-click sample-template buttons that pre-fill the text area for live demos.
  - Free-form text area accepting any of the three supported languages.
  - Animated processing card (pulsing CSS dot) shown while parsing runs.
  - **Left card — Extracted Trade Parameters:** cluster, monthly volume, payment latency, loan request — green if detected, grey-italic if missing.
  - **Right card — Localized Agent Recommendation:** credit score + translated band badge, MUDRA/PM Vishwakarma scheme name in target language, confidence %, translated risk flags and eligibility gaps.
  - Raw parser + router JSON expander for transparency.
- `TRANSLATIONS` dict provides all UI strings in three languages (labels, placeholders, band names, scheme names).
- `_t_flag` / `_t_gap` helpers post-translate predictable risk/gap strings; duplicate translated gaps deduplicated.
- `_build_synthetic_profile()` converts parsed fields to a real `CreditProfile` and passes it to the existing `route_artisan()` — live scheme routing against the DB, no mocked output.

### Extraction accuracy on built-in samples

| Language | Cluster | Turnover | Latency | Loan |
|----------|---------|----------|---------|------|
| English | Chowk | ₹45K | 60 days | ₹80K |
| Hindi (हिन्दी) | Chowk | ₹35K | 60 days | ₹1.00L |
| Awadhi (अवधी) | Aminabad | ₹40K | 60 days | ₹50K |

### Key decisions
- Parser uses ordered rule lists with `(pattern, is_lakh_direct)` metadata so lakh expansion is applied before the ≥ ₹1,000 sanity check — prevents `1.0 < 1000` false-reject on "1 लाख" inputs.
- Synthetic `CreditProfile` uses a latency → `(fast_rate, default_rate, CV)` lookup table so score estimates are deterministic and explainable without any ML model.
- Language state lives in `st.session_state["interface_lang"]` via a sidebar radio; switching languages never causes a state crash because all UI strings are looked up from `TRANSLATIONS[lang]` at render time.

### Next steps
- [ ] Add `pytest` test suite for scoring math, router hard-gate logic, and parser extraction accuracy.
- [ ] Expose `score_artisan` + `route_artisan` via a lightweight FastAPI layer.
- [ ] Explore adding a bureau-pull simulation (CIBIL stub) as a fourth scoring input.
- [ ] Extend parser to extract artisan name and craft type from unstructured text.
- [ ] Add Gujarati / Bhojpuri dialect support as additional language options.

---

## Session 5 — 2026-05-22

**Goal:** Complete UI/UX enterprise fintech dark-mode overhaul of `app.py` — transform the dashboard into a premium financial SaaS interface suitable for institutional underwriters.

### Built

**`app.py`** (complete rewrite, ~1,540 lines)
- Massive CSS dark theme injected via `st.markdown(unsafe_allow_html=True)`:
  - Palette: `#0E1117` (bg) · `#1A1D24` (card surface) · `#38BDF8` (sky accent) · `#10B981` (emerald success) · `#F59E0B` (amber warning) · `#EF4444` (red danger) · `#2E323D` (border)
  - CSS classes: `.dash-header`, `.exec-metric`, `.risk-badge` (five tiers), `.signal-card`, `.scheme-block`, `.flag-item`, `.gap-item`, `.ob-card`, `.empty-state`, `.ob-processing` (pulsing keyframe animation)
- **Dashboard tab:**
  - Header bar showing artisan name, craft, cluster + risk band badge
  - 4-column Executive Summary Matrix: Credit Score · Algorithmic Confidence · Capital Ceiling · Prompt Settlement Rate
  - 60/40 column split (`st.columns([3, 2])`)
  - Left column (60%) — 3 inner tabs:
    - **📊 Multilingual Parser** — Plotly gauge + sub-score bar chart (side-by-side) + 3 signal decomposition cards (Cash Flow / Fulfillment / Relationship), each showing score/100, weight %, 3 KV rows, grade tag
    - **📈 Invoicing Timeline** — seasonality-adjusted revenue line chart + payment latency bar chart; dark `_DARK_LAYOUT` / `_AXIS_STYLE` shared dicts; professional empty states (◈ icon)
    - **🗃️ Ledger SQL Logs** — GST invoice + order ledger dataframes (most recent 30 rows)
  - Right column (40%) — Underwriting Suite: scheme block (green gradient), confidence progress bar, KV inputs, risk flags, eligibility gaps, raw JSON expander
- **Smart Onboarding tab:** dark CSS classes throughout; ◈ empty state when no analysis has run
- Shared Plotly dark helpers: `_DARK_LAYOUT` and `_AXIS_STYLE` dicts eliminate per-chart boilerplate

**`.streamlit/config.toml`** (new file)
- Forces `base = "dark"` so native Streamlit components (dataframes, progress bars, text areas) match the injected CSS palette
- Sets `primaryColor = "#38BDF8"`, `backgroundColor = "#0E1117"`, `secondaryBackgroundColor = "#1A1D24"`, `textColor = "#F1F5F9"`

### Key decisions
- Two complementary theming layers: `.streamlit/config.toml` for Streamlit-native widgets + CSS injection for custom HTML components.
- Shared `_DARK_LAYOUT` / `_AXIS_STYLE` dicts avoid repeating dark-mode Plotly config on each chart.
- `score_meta()` returns `(label, css_class, hex_color)` so badge, chart color, and card accent all derive from one call.
- Inner tabs in the left column keep the 60/40 layout stable while maximising the data surface area visible at once.

### Bugfixes
- **Gauge chart crash (`ValueError: Invalid property 'linecolor'`)** — `linecolor` is not a valid property on `plotly.graph_objs.indicator.gauge.Axis` (valid on XY axes, not indicator gauges). Removed from `chart_gauge()`.

### Next steps
- [ ] Add `pytest` test suite for scoring math, router hard-gate logic, and parser extraction accuracy.
- [ ] Expose `score_artisan` + `route_artisan` via a lightweight FastAPI layer.
- [ ] Explore adding a bureau-pull simulation (CIBIL stub) as a fourth scoring input.
- [ ] Extend parser to extract artisan name and craft type from unstructured text.
- [ ] Add Gujarati / Bhojpuri dialect support as additional language options.

---
## Session 6 — 2026-05-22

**Goal:** Implement a secure, state-managed authentication system, multi-role dashboard routing, and an immutable audit logging system into `app.py`.

### Built

**`app.py`** (complete rewrite, ~1,750 lines)

#### 1. Session State Authentication Core
- Login screen rendered via `_render_login()` if `auth_authenticated` is absent from `st.session_state`. `st.stop()` blocks all app content until authenticated — no partial renders possible.
- Passwords stored as `hashlib.sha256` hex digests in a hardcoded `USERS` config dict. No external OAuth library.
- Two role credentials (both `password123`):
  - `manager` → **Bank Underwriter** / `[Institutional Underwriter]` — full access to all tabs
  - `assistant` → **Artisan Assistant / NGO Facilitator** / `[NGO Facilitator]` — Smart Onboarding tab only
- Demo credential hint rendered below the form for judges.
- Logout clears all `st.session_state` keys and calls `st.rerun()` — returns instantly to unauthenticated state with no rendering loops.

#### 2. Multi-Role View Router
- Sidebar shows an **account status banner** (display name + role tier) and a **Log Out** button for every authenticated session.
- Role-aware tab creation:
  - `manager` → 3 tabs: `📊 Credit Dashboard`, `🗣️ Smart Onboarding`, `🔒 Audit Logs`
  - `assistant` → 1 tab: `🗣️ Smart Onboarding`
- All dashboard and audit tab content additionally guarded by `if _is_manager:` so URL-pattern tricks cannot bypass the gate.
- Artisan directory sidebar section only renders for manager role.

#### 3. Immutable Audit Logging System
- `audit_logs` table created idempotently in `artisan_credit.db` via `_init_audit_table()` on every authenticated load.
- `_log_action()` appends rows with UTC ISO timestamps; wrapped in `try/except` so logging never crashes the app.
- Three logged events: `CREDIT_SCORE_VIEWED` (per artisan switch), `STATEMENT_ANALYZED` (per analyze click), `UNDERWRITING_KIT_EXPORTED` (explicit download button).
- **Audit Logs tab** (manager only): summary stat cards + immutable `st.dataframe` sorted newest-first.

#### 4. CSS additions
New classes: `.auth-wrap`, `.auth-banner`, `.auth-banner-tier`, `.perm-error`, `.audit-stat`.

### Key decisions
- Auth guard placed after DB guard — missing DB shows the appropriate error, not a login prompt.
- `_load_audit_logs()` deliberately NOT decorated with `@st.cache_data` so the audit tab always reflects the latest rows.
- `artisan_id` never assigned in the assistant path — all uses sit inside the same `if _is_manager:` guard, no `NameError` risk.

### Next steps
- [ ] Add `pytest` test suite for scoring math, router hard-gate logic, and parser extraction accuracy.
- [ ] Expose `score_artisan` + `route_artisan` via a lightweight FastAPI layer.
- [ ] Explore adding a bureau-pull simulation (CIBIL stub) as a fourth scoring input.
- [ ] Extend parser to extract artisan name and craft type from unstructured text.
- [ ] Add Gujarati / Bhojpuri dialect support as additional language options.

---

## Session 7 — 2026-05-31

**Goal:** Add a game-winning demo feature — a WhatsApp Business Simulation Sandbox — that shows the system acting as a real-time backend listener to WhatsApp media messages, runs OCR extraction, and persists new records to the live SQLite database.

### Built

**`app.py`** (extended, +386 lines)

#### 1. WhatsApp Smartphone UI (`💬 WhatsApp Sandbox` tab)
- New tab added to both role paths: `manager` (4 tabs: Dashboard / Onboarding / WhatsApp / Audit) and `assistant` (2 tabs: Onboarding / WhatsApp).
- Full smartphone frame rendered in pure CSS/HTML: `#E5DDD5` chat background (WhatsApp brand colour), `#075E54` dark-green header bar with status row, scrollable `.wa-body` chat area, decorative input bar.
- Two bubble classes: `.wa-in` (white, left-aligned — agent) and `.wa-out` (`#DCF8C6` green, right-aligned — artisan), each with timestamps and read-tick markers (`✓` / `✓✓`).
- Initial conversation seeded statically (agent greeting → artisan confirms → SmartScan™ activation message).
- After OCR ingest, 5 new messages render into the thread: attachment bubble → "Vision Analytics Pipeline processing" status → extraction summary card → "Database Updated!" confirmation → artisan thank-you. Thread re-renders entirely from session state on each `st.rerun()`.

#### 2. OCR & Media Ingest Simulator
- **Artisan picker:** `st.selectbox` over all 50 live artisans; invoice is written under the chosen artisan's ID so the Credit Dashboard update is visible for any selected record.
- **Sample scan selector:** two pre-loaded document simulations:
  - `Handwritten Khata Bill.jpg · Chowk Cluster` — Hindi-script Khata receipt for ₹18,500 Chikankari invoice, 45-day terms, buyer "Lucknow Chikankari House".
  - `Logistics Dispatch Note.png · Aminabad Cluster` — English dispatch note for ₹42,000 Zardozi order, 60-day terms, buyer "Craftroot Exports".
- 1.5-second `st.spinner("Processing Image via Vision Analytics Pipeline…")` simulates Vision API latency before the DB write.

#### 3. Real Database Write + Cache Bust
- `_wa_insert_invoice(artisan_id, buyer, value, overdue_days)` helper:
  - Generates a unique invoice number `WA-{artisan_id:03d}-{uuid4 hex[:8].upper()}` with today's date.
  - Computes 5% GST and maps overdue_days to `Paid` / `Pending` / `Overdue` status.
  - Inserts one row into `gst_invoices` via a direct `sqlite3.connect` write.
  - Calls `load_profile.clear()`, `load_invoices.clear()`, `load_routing.clear()` — busts all per-artisan Streamlit cache entries so the Credit Dashboard reflects the new record immediately.
- Every ingest is logged as `WHATSAPP_OCR_INGEST` in `audit_logs` — visible in the Audit Logs tab.

#### 4. Extraction Results Panel
- OCR raw text displayed in a monospace `.wa-ocr-text` block (dark `#0D1117` background, `SF Mono` / `Courier New` font).
- `language_parser.parse_trade_statement()` runs on the embedded statement text; `_build_synthetic_profile()` converts the `ParsedStatement` to a `CreditProfile` to show the estimated credit score.
- KV table shows: Cluster Detected, Monthly Turnover, Payment Latency, Invoice Value, Buyer, Est. Credit Score, Inserted Invoice #, Artisan Record.
- Pulsing green `wa-dot` success banner: *"Database Updated Successfully via WhatsApp Stream! Underwriter Dashboard refreshed live."*
- Cross-tab prompt tells the judge exactly which artisan to select in the Credit Dashboard to see the updated invoice count and recalculated score.
- **↺ Reset Sandbox** button clears all `wa_*` session-state keys and calls `st.rerun()` — restores the phone to its initial state.

#### 5. New CSS classes (added to global style block)
`.wa-phone`, `.wa-status`, `.wa-header`, `.wa-avatar`, `.wa-cname`, `.wa-cstat`, `.wa-body`, `.wa-divider`, `.wa-in`, `.wa-out`, `.wa-ts`, `.wa-ts-r`, `.wa-attach`, `.wa-bar`, `.wa-pill`, `.wa-send`, `.wa-ocr-panel`, `.wa-ocr-hdr`, `.wa-ocr-text`, `.wa-success`, `.wa-dot` (`@keyframes wa-blink`), `.wa-kv`, `.wa-kv-k`, `.wa-kv-v`.

### Verified
- `python3 -m py_compile app.py` — no syntax errors.
- End-to-end DB write confirmed: artisan 1 invoice count incremented from 55 → 56; `score_artisan` returned updated `total_invoices=56` without restarting the app.
- All sample parse targets (Chowk/Khata, Aminabad/Dispatch) extracted correct cluster, turnover, and latency values.

### Key decisions
- `_wa_insert_invoice` placed after the cached loaders so `load_profile.clear()` etc. are in scope at definition time; the function is only called at Streamlit runtime, not at module-load time, so ordering is safe.
- Phone frame is pure `st.markdown(unsafe_allow_html=True)` — no additional `streamlit-elements` or JS dependency.
- `_WA_SAMPLES` stores OCR raw text (displayed verbatim) and a natural-language statement (fed to `language_parser`) as separate keys — raw text looks like imperfect scanner output while the statement is grammar-correct for reliable parsing.
- Per-function `.clear()` calls rather than global `st.cache_data.clear()` — only artisan-level caches are invalidated; artisan list and chart config caches remain warm.

### Next steps
- [ ] Add `pytest` test suite for scoring math, router hard-gate logic, and parser extraction accuracy.
- [ ] Expose `score_artisan` + `route_artisan` via a lightweight FastAPI layer.
- [ ] Explore adding a bureau-pull simulation (CIBIL stub) as a fourth scoring input.
- [ ] Extend parser to extract artisan name and craft type from unstructured text.
- [ ] Add Gujarati / Bhojpuri dialect support as additional language options.

---

## Session 8 — 2026-05-31

**Goal:** Complete UI/UX overhaul to match the KarigarCred design spec — migrating from the custom dark theme to a production-grade design system with IBM Plex fonts, CSS variable tokens, indigo accent, and a fully redesigned component library.

### Built

**`app.py`** (complete redesign, +381 net lines)

#### 1. KarigarCred Design System
- CSS variable token system injected on `body` — two complete palettes (dark and light), toggled by `st.session_state["kc_dark"]` at runtime without a page reload.
- Dark tokens: `--bg:#0c0e13` · `--surface:#14171e` · `--accent:#4f46d6` (indigo) · five risk tiers (`--t-prime` → `--t-sub`).
- Light tokens: `--bg:#f1f1ec` · `--surface:#ffffff` · same accent and tier variables with higher-contrast hex values.
- Fonts: **IBM Plex Sans** (UI) + **IBM Plex Mono** (numbers, data, monospace labels) + **Noto Sans Devanagari** (Hindi / Awadhi scripts), all loaded via Google Fonts `@import`.

#### 2. Light / Dark Mode Toggle
- ☾ / ☀ button in the sidebar header row persists `kc_dark` in session state and calls `st.rerun()` — the entire app re-renders with the opposite CSS variable set and Plotly chart colours.
- Plotly chart accent, grid, and tick colours are computed from `_kc_dark` at module load and passed into `_DARK_LAYOUT` / `_AXIS_STYLE`.

#### 3. KarigarCred Brand Header
- New top-of-dashboard `kc-brand-header` bar: `◈` logo mark, "KarigarCred" wordmark, "INSTITUTIONAL UNDERWRITING TERMINAL" sub-label.
- Centre: live status pill — `●` dot (CSS box-shadow glow), `LIVE · artisan_credit.db / Lucknow MSME cohort`.
- Right: user avatar chip showing initials `BU`, display name, and role tier.

#### 4. Cohort Strip
- Horizontally segmented 6-cell strip rendered above the artisan subject bar:
  - Five stat cells: Portfolio (50), GST invoices (live count), Ledger rows (live count), Mean score (686, 501–790 range), Scheme-matched (50/50).
  - Sixth cell: Scheme coverage mini-bars — MUDRA Kishor 68 % · MUDRA Shishu 28 % · PM Vishwakarma 4 %, each coloured with its risk-tier variable.

#### 5. Subject Bar
- Replaced flat `.dash-header` with `kc-subject`: large artisan name + chip row (`ART-XXXX` · cluster · craft type · years active · card status).
- Risk band badge is a **bordered pill** (`kc-band-badge`) styled inline from `band_color` — e.g. `● T2 · Strong` in the exact tier colour.

#### 6. 6-Column Executive Matrix
- Expanded from 4 → 6 columns: adds **Default Rate** (24-month window, coloured red when > 15 %) and **Repeat-Buyer Share** (order ledger).
- First cell has a left accent bar in `--accent`; all values use IBM Plex Mono for tabular alignment.

#### 7. Composite Credit Assessment Panel
- New section above the inner tabs: gauge chart (left) + sub-score horizontal bars (right) in `st.columns([1, 1.4])`.
- Sub-score bars and gauge needle use the artisan's current band colour.

#### 8. Signal Decomposition Cards (A/B/C/D/E grades)
- Inner tab renamed from "Multilingual Parser" → **Signal Decomposition**.
- Three `kc-sig` cards: Cash-Flow Stability (30 %) · Invoice Fulfillment (40 %) · Trade Relationship (30 %).
- Each card: title + weight badge, large score `/100`, letter grade A–E (colour-coded), three KV data rows.
- `sig_grade(v)` helper: A ≥ 82 · B ≥ 70 · C ≥ 58 · D ≥ 46 · E < 46.

#### 9. Underwriting Suite Redesign
- `kc-uw-panel`: header row with tier tag, `kc-scheme-block` (indigo-tinted, eyebrow + name + loan range + confidence bar), alternative facilities list with coloured dots, 2-column callout grid (risk signals / eligibility gaps).
- "Export Underwriting Kit" rendered as `st.button(type="primary")`.

#### 10. Smart Onboarding — KarigarCred Field Assistant
- Field Assistant eyebrow + segmented language control (3 `st.button` columns).
- Extracted parameters card with ✓/✕ check icons and "4/4" count badge.
- Recommendation card: large score + bordered band badge, scheme + confidence bar, per-item callout rows.
- New **Push to Underwriter** button with success feedback.

#### 11. Updated Risk Bands
- `score_meta()` rewritten for 5 new tiers: Prime ≥ 760 · Strong ≥ 720 · Standard ≥ 660 · Watch ≥ 580 · Sub-prime < 580.
- `score_tier()` returns `T1`–`T5` for the band badge.

#### 12. `.streamlit/config.toml`
- `primaryColor` → `#4f46d6`, `backgroundColor` → `#0c0e13`, `secondaryBackgroundColor` → `#14171e`, `textColor` → `#eef1f6`.

### Verified
- `python3 -m py_compile app.py` — no syntax errors.
- App starts and all tabs render without runtime exceptions.
- Dashboard, cohort strip, subject bar, exec matrix, signal cards, and underwriting suite confirmed via Playwright screenshot.
- Dark mode toggle persists across artisan switches.

### Key decisions
- CSS tokens injected via a small f-string separate from the main component CSS block (plain triple-quoted string) — avoids escaping hundreds of CSS curly braces.
- Underwriting Suite split into four `st.markdown()` calls — Streamlit handles smaller, self-contained HTML blocks more reliably than one giant f-string.
- `sig_grade()` and `score_tier()` as standalone helpers so signal cards and subject bar share consistent grading logic.
- Plotly chart colours derived from `_kc_dark` flag to match the active theme.

### Next steps
- [ ] Add `pytest` test suite for scoring math, router hard-gate logic, and parser extraction accuracy.
- [ ] Expose `score_artisan` + `route_artisan` via a lightweight FastAPI layer.
- [ ] Explore adding a bureau-pull simulation (CIBIL stub) as a fourth scoring input.
- [ ] Extend parser to extract artisan name and craft type from unstructured text.
- [ ] Add Gujarati / Bhojpuri dialect support as additional language options.
