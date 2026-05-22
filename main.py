"""
main.py
-------
Integration entry-point for the Lucknow Artisan Credit Scoring System.

Pipeline:
  1. Drop and re-create the SQLite database.
  2. Populate it with 50 synthetic artisan profiles + transactions.
  3. Run the scoring engine across all 50 artisans.
  4. Print a cohort-level credit score distribution summary.
  5. Select 5 representative archetypes (top / Q1 / median / Q3 / bottom)
     and print a full per-artisan card with sub-scores, scheme recommendation,
     risk flags, and eligibility gaps.
  6. Print a scheme coverage table across the full cohort.

All output is Markdown-formatted so it can be piped directly into a report.
"""

import os
from collections import Counter

from artisan_credit.agent_router import route_artisan
from artisan_credit.data_generator import populate_database
from artisan_credit.scoring_engine import CreditProfile, score_all_artisans

DB_PATH = "artisan_credit.db"


# ─────────────────────────────────────────────────────────────────────────────
# Formatting helpers
# ─────────────────────────────────────────────────────────────────────────────

def _score_band(score: int) -> str:
    if score >= 750:
        return "Prime"
    elif score >= 650:
        return "Near-Prime"
    elif score >= 550:
        return "Subprime"
    elif score >= 450:
        return "Deep Subprime"
    return "Credit Invisible"


def _fmt_inr(value: float) -> str:
    if value >= 1_00_00_000:
        return f"₹{value / 1_00_00_000:.2f}Cr"
    if value >= 1_00_000:
        return f"₹{value / 1_00_000:.2f}L"
    if value >= 1_000:
        return f"₹{value / 1_000:.1f}K"
    return f"₹{value:.0f}"


# ─────────────────────────────────────────────────────────────────────────────
# Report sections
# ─────────────────────────────────────────────────────────────────────────────

def print_population_summary(profiles: list[CreditProfile]) -> None:
    scores = [p.credit_score for p in profiles]
    avg = sum(scores) / len(scores)
    band_counts: Counter[str] = Counter(_score_band(s) for s in scores)

    print("## Population Credit Score Summary\n")
    print("| Metric | Value |")
    print("|--------|-------|")
    print(f"| Total artisans scored | {len(profiles)} |")
    print(f"| Mean credit score | {avg:.0f} |")
    print(f"| Highest score | {max(scores)} |")
    print(f"| Lowest score  | {min(scores)} |")
    print()

    print("### Score Band Distribution\n")
    print("| Band | Count | % of cohort |")
    print("|------|-------|-------------|")
    for band in ("Prime", "Near-Prime", "Subprime", "Deep Subprime", "Credit Invisible"):
        count = band_counts.get(band, 0)
        pct = 100.0 * count / len(profiles)
        print(f"| {band} | {count} | {pct:.0f}% |")
    print()


def print_profile_card(profile: CreditProfile, routing: dict) -> None:
    band = _score_band(profile.credit_score)
    print(f"### {profile.name}  —  Score **{profile.credit_score}** ({band})\n")

    print("| Field | Value |")
    print("|-------|-------|")
    print(f"| Cluster | {profile.cluster} |")
    print(f"| Craft | {profile.craft_type} |")
    print(f"| Artisan card | {profile.artisan_card_status} |")
    print(f"| Years active | {profile.years_active} |")
    print(f"| Annual turnover | {_fmt_inr(profile.annual_turnover)} |")
    print(f"| Avg monthly revenue | {_fmt_inr(profile.avg_monthly_revenue)} |")
    print(f"| Revenue CV (adj) | {profile.revenue_cv_adjusted:.3f} |")
    print(f"| Fast-payment rate (≤45d) | {profile.fast_payment_rate:.0%} |")
    print(f"| Severe-default rate (>90d) | {profile.severe_default_rate:.0%} |")
    print(f"| Repeat-buyer order share | {profile.repeat_buyer_rate:.0%} |")
    print(f"| Unique buyers (ledger) | {profile.unique_buyers} |")
    print(f"| Total GST invoices | {profile.total_invoices} |")
    print()

    print("**Sub-scores**\n")
    print("| Component | Weight | Raw score |")
    print("|-----------|--------|-----------|")
    print(f"| Cash flow consistency | 30% | {profile.cashflow_score:.1f} / 100 |")
    print(f"| Invoice fulfillment   | 40% | {profile.fulfillment_score:.1f} / 100 |")
    print(f"| Trade relationship    | 30% | {profile.relationship_score:.1f} / 100 |")
    print(f"| **Composite**         | 100% | **{profile.composite_raw:.1f} / 100** |")
    print()

    rec   = routing.get("recommended_scheme") or "None"
    amt   = routing.get("max_eligible_loan_amount", 0.0)
    conf  = routing.get("confidence_score", 0.0)
    alts  = routing.get("alternative_schemes", [])

    print("**Scheme Recommendation**\n")
    print("| Field | Value |")
    print("|-------|-------|")
    print(f"| Recommended scheme | {rec} |")
    print(f"| Max eligible loan  | {_fmt_inr(amt)} |")
    print(f"| Confidence score   | {conf:.0%} |")
    if alts:
        print(f"| Alternative schemes | {', '.join(alts)} |")
    print()

    flags   = profile.risk_flags
    missing = routing.get("missing_parameters", [])

    if flags:
        print("**Risk Flags**\n")
        for f in flags:
            print(f"- {f}")
        print()

    if missing:
        print("**Eligibility Gaps**\n")
        for g in missing:
            print(f"- {g}")
        print()

    print("---\n")


def print_scheme_coverage(profiles: list[CreditProfile]) -> None:
    scheme_counts: Counter[str] = Counter()
    ineligible = 0

    for p in profiles:
        r = route_artisan(p, DB_PATH)
        rec = r.get("recommended_scheme")
        if rec:
            scheme_counts[rec] += 1
        else:
            ineligible += 1

    print("## Scheme Coverage — Full Cohort\n")
    print("| Scheme | Artisans matched |")
    print("|--------|-----------------|")
    for scheme, count in scheme_counts.most_common():
        print(f"| {scheme} | {count} |")
    if ineligible:
        print(f"| No eligible scheme | {ineligible} |")
    print()

    total_eligible = sum(scheme_counts.values())
    print(
        f"> **{total_eligible} of {len(profiles)} artisans** matched to at least one "
        f"government credit scheme.\n"
    )


def _select_representative_profiles(profiles: list[CreditProfile]) -> list[CreditProfile]:
    """Return 5 profiles spanning the score distribution: top, Q1, median, Q3, bottom."""
    ranked = sorted(profiles, key=lambda p: p.credit_score, reverse=True)
    n = len(ranked)
    indices = [0, n // 4, n // 2, 3 * n // 4, n - 1]
    return [ranked[i] for i in indices]


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    print(f"# Lucknow Artisan Credit Scoring System\n")
    print(f"> Initialising database at `{DB_PATH}`\n")
    populate_database(DB_PATH)
    print()

    print("> Running scoring engine across all artisans…\n")
    profiles = score_all_artisans(DB_PATH)
    print()

    print_population_summary(profiles)

    print("## Representative Artisan Profiles\n")
    print(
        "> Showing five archetypes: highest scorer · upper quartile · "
        "median · lower quartile · lowest scorer\n"
    )
    print("---\n")

    for profile in _select_representative_profiles(profiles):
        routing = route_artisan(profile, DB_PATH)
        print_profile_card(profile, routing)

    print_scheme_coverage(profiles)


if __name__ == "__main__":
    main()
