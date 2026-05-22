"""
agent_router.py
---------------
Agentic eligibility router: maps a CreditProfile to the optimal government
loan scheme by querying live scheme rules from the SQLite database.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ROUTING LOGIC (executed in order)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Step 1 — Fetch all schemes from govt_schemes ordered by max_loan_amount DESC
            (highest-value schemes evaluated first to surface best outcomes).

  Step 2 — Hard-gate check per scheme:
              • credit_score ≥ scheme.min_credit_score
              • annual_turnover ≥ scheme.min_annual_turnover
              • annual_turnover ≤ scheme.max_annual_turnover  (if not NULL)
              • artisan_card_status ∈ {Active, Pending}        (if required)
              • years_active ≥ scheme.min_years_active

  Step 3 — Confidence score (0–1.0) for each passing scheme:
              credit_component   = 0.40 × headroom_fraction
                where headroom_fraction = (score − min_score) / (850 − min_score)
              turnover_component = 0.35 × bracket_centrality
                where bracket_centrality = 1 − |position − 0.5| × 2
                and   position           = (turnover − min_t) / (max_t − min_t)
                (penalises artisans at the extremes of a bracket)
              card_component     = 0.25 if Active | 0.15 if Pending | 0.05 otherwise

  Step 4 — Select highest-confidence scheme as recommendation.
            All other passing schemes are listed as alternatives.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT JSON CONTRACT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  {
    "artisan_id":              int,
    "artisan_name":            str,
    "credit_score":            int,
    "recommended_scheme":      str | null,
    "max_eligible_loan_amount": float,      // ₹ amount
    "confidence_score":        float,       // 0.0 – 1.0
    "alternative_schemes":     [str],
    "missing_parameters":      [str],       // unmet hard-gate criteria
    "risk_flags":              [str]        // from CreditProfile
  }
"""

import json
import sqlite3
from typing import Any

import pandas as pd

from scoring_engine import CreditProfile


def _hard_gate_gaps(profile: CreditProfile, scheme: pd.Series) -> list[str]:
    """
    Return list of unmet hard eligibility criteria for this scheme.
    Empty list ⟹ artisan passes all gates and scheme is eligible.
    """
    gaps: list[str] = []

    if profile.credit_score < int(scheme["min_credit_score"]):
        gaps.append(
            f"Credit score {profile.credit_score} below {scheme['scheme_name']} "
            f"minimum of {int(scheme['min_credit_score'])}"
        )

    if profile.annual_turnover < float(scheme["min_annual_turnover"]):
        gaps.append(
            f"Annual turnover ₹{profile.annual_turnover:,.0f} below {scheme['scheme_name']} "
            f"minimum of ₹{float(scheme['min_annual_turnover']):,.0f}"
        )

    if scheme["max_annual_turnover"] is not None:
        if profile.annual_turnover > float(scheme["max_annual_turnover"]):
            gaps.append(
                f"Annual turnover ₹{profile.annual_turnover:,.0f} exceeds {scheme['scheme_name']} "
                f"cap of ₹{float(scheme['max_annual_turnover']):,.0f}"
            )

    if int(scheme["requires_artisan_card"]) == 1:
        if profile.artisan_card_status not in ("Active", "Pending"):
            gaps.append(
                f"{scheme['scheme_name']} requires an active or pending artisan card "
                f"(current status: {profile.artisan_card_status})"
            )

    if profile.years_active < int(scheme["min_years_active"]):
        gaps.append(
            f"Years active ({profile.years_active}) below {scheme['scheme_name']} "
            f"minimum of {int(scheme['min_years_active'])}"
        )

    return gaps


def _confidence(profile: CreditProfile, scheme: pd.Series) -> float:
    """
    Compute a 0–1 confidence that this scheme is the optimal fit.
    See module docstring Step 3 for the formula derivation.
    """
    # Credit headroom component (0–0.40)
    score_range = max(1, 850 - int(scheme["min_credit_score"]))
    headroom = (profile.credit_score - int(scheme["min_credit_score"])) / score_range
    credit_component = 0.40 * float(min(1.0, max(0.0, headroom)))

    # Turnover bracket centrality component (0–0.35)
    min_t = float(scheme["min_annual_turnover"])
    max_t = (
        float(scheme["max_annual_turnover"])
        if scheme["max_annual_turnover"] is not None
        else profile.annual_turnover * 2.0
    )
    bracket_width = max(1.0, max_t - min_t)
    position = (profile.annual_turnover - min_t) / bracket_width
    centrality = 1.0 - abs(position - 0.5) * 2.0
    turnover_component = 0.35 * float(max(0.0, centrality))

    # Artisan card component (0–0.25)
    card_map = {"Active": 0.25, "Pending": 0.15}
    card_component = card_map.get(profile.artisan_card_status, 0.05)

    return round(credit_component + turnover_component + card_component, 4)


def route_artisan(
    profile: CreditProfile,
    db_path: str = "artisan_credit.db",
) -> dict[str, Any]:
    """
    Execute the eligibility routing pipeline and return a structured recommendation.

    Parameters
    ----------
    profile : CreditProfile
        Fully computed profile from scoring_engine.score_artisan().
    db_path : str
        Path to the SQLite database containing govt_schemes.

    Returns
    -------
    dict matching the JSON contract defined in this module's docstring.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    schemes = pd.read_sql(
        "SELECT * FROM govt_schemes ORDER BY max_loan_amount DESC", conn
    )
    conn.close()

    eligible: list[tuple[float, pd.Series]] = []
    all_gaps: list[str] = []

    for _, scheme in schemes.iterrows():
        gaps = _hard_gate_gaps(profile, scheme)
        if not gaps:
            eligible.append((_confidence(profile, scheme), scheme))
        else:
            all_gaps.extend(gaps)

    # Deduplicate gap messages while preserving insertion order.
    seen_gaps: set[str] = set()
    unique_gaps: list[str] = []
    for g in all_gaps:
        if g not in seen_gaps:
            seen_gaps.add(g)
            unique_gaps.append(g)

    if not eligible:
        return {
            "artisan_id":               profile.artisan_id,
            "artisan_name":             profile.name,
            "credit_score":             profile.credit_score,
            "recommended_scheme":       None,
            "max_eligible_loan_amount": 0.0,
            "confidence_score":         0.0,
            "alternative_schemes":      [],
            "missing_parameters":       unique_gaps,
            "risk_flags":               profile.risk_flags,
        }

    eligible.sort(key=lambda x: x[0], reverse=True)
    best_conf, best_scheme = eligible[0]
    alternatives = [str(s["scheme_name"]) for _, s in eligible[1:]]

    return {
        "artisan_id":               profile.artisan_id,
        "artisan_name":             profile.name,
        "credit_score":             profile.credit_score,
        "recommended_scheme":       str(best_scheme["scheme_name"]),
        "max_eligible_loan_amount": float(best_scheme["max_loan_amount"]),
        "confidence_score":         float(best_conf),
        "alternative_schemes":      alternatives,
        "missing_parameters":       unique_gaps,
        "risk_flags":               profile.risk_flags,
    }


def route_artisan_json(
    profile: CreditProfile,
    db_path: str = "artisan_credit.db",
) -> str:
    """Convenience wrapper returning a formatted JSON string."""
    return json.dumps(route_artisan(profile, db_path), indent=2, ensure_ascii=False)
