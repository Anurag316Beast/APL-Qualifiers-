"""
language_parser.py
------------------
Regex + keyword parser for multilingual artisan trade statements.
Supports English, Hindi (हिन्दी), and Awadhi (अवधी) — no external API required.

Extracted fields
────────────────
  cluster              str | None   – "Chowk" | "Aminabad" | None
  monthly_turnover     float | None – INR
  payment_latency_days int   | None – days
  loan_amount          float | None – INR requested
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedStatement:
    cluster:              Optional[str]
    monthly_turnover:     Optional[float]
    payment_latency_days: Optional[int]
    loan_amount:          Optional[float]
    raw_text:             str


# ── Number-word → integer (English + Hindi + Awadhi) ─────────────────────────
_WORD_TO_INT: dict[str, int] = {
    "one": 1,  "two": 2,   "three": 3, "four": 4,  "five": 5,
    "six": 6,  "seven": 7, "eight": 8, "nine": 9,  "ten": 10,
    "एक": 1,   "दो": 2,    "तीन": 3,   "चार": 4,   "पाँच": 5,
    "छह": 6,   "सात": 7,   "आठ": 8,    "नौ": 9,    "दस": 10,
    "दुई": 2,  "दुइ": 2,   "तिन": 3,
}

# alternation string used inside latency patterns
_WORD_ALT = "|".join(re.escape(k) for k in _WORD_TO_INT)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _to_float(raw: str) -> Optional[float]:
    try:
        return float(raw.replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def _expand_lakh(value: float, ctx: str) -> float:
    """Multiply value by 1,00,000 if 'lakh' or 'लाख' appears in ctx."""
    if re.search(r"लाख|lakh", ctx, re.IGNORECASE):
        return value * 1_00_000
    return value


# ── Cluster ───────────────────────────────────────────────────────────────────

_CLUSTER_PATTERNS: dict[str, list[str]] = {
    "Chowk":    [r"\bchowk\b", r"चौक"],
    "Aminabad": [r"\baminabad\b", r"अमिनाबाद", r"अमीनाबाद"],
}


def _extract_cluster(text: str) -> Optional[str]:
    for cluster, pats in _CLUSTER_PATTERNS.items():
        for pat in pats:
            if re.search(pat, text, re.IGNORECASE):
                return cluster
    return None


# ── Monthly turnover ──────────────────────────────────────────────────────────
# (pattern, multiply_by_lakh_directly)
_TURNOVER_RULES: list[tuple[str, bool]] = [
    # English: "monthly sales on invoices are around 45,000 rupees"
    (r"monthly\s+(?:sales|revenue|invoice\w*|turnover)"
     r"(?:\s+\w+){0,8}\s+([\d][\d,]*(?:\.\d+)?)", False),
    # Hindi: "महीने का 35,000 रुपये"
    (r"महीने\s+का\s+([\d][\d,]*(?:\.\d+)?)", False),
    # Hindi: "35,000 रुपये का इनवॉइस"
    (r"([\d][\d,]*(?:\.\d+)?)\s*(?:रुपये|रुपिया)\s+का\s+इनवॉइस", False),
    # Awadhi: "महीनवा मा करीब 40,000"
    (r"महीनवा\s+मा\s+करीब\s+([\d][\d,]*(?:\.\d+)?)", False),
    # Lakh turnover: "monthly 2 lakh" / "महीने 2 लाख"
    (r"(?:महीने?\s+(?:का|मा)|monthly)\s+([\d][\d,]*(?:\.\d+)?)\s*(?:लाख|lakh)", True),
]


def _extract_monthly_turnover(text: str) -> Optional[float]:
    for pat, is_lakh in _TURNOVER_RULES:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = _to_float(m.group(1))
            if val and val >= 500:
                if is_lakh:
                    return val * 1_00_000
                ctx = text[max(0, m.start(1) - 3): m.end(1) + 12]
                return _expand_lakh(val, ctx)
    return None


# ── Payment latency ───────────────────────────────────────────────────────────

_LATENCY_DAY_RULES: list[str] = [
    r"after\s+(\d+)\s+days?",
    r"(\d+)\s*-?\s*days?\s+(?:credit|payment|later|after|delay)",
    r"(?:bills?|invoice\w*|payment\w*)\s+(?:clear\w*\s+)?after\s+(\d+)\s+days?",
    r"(\d+)\s+दिन\s+(?:बाद|में|के\s+बाद)",
]

_LATENCY_MONTH_RULES: list[str] = [
    r"after\s+(\d+)\s+months?",
    r"(\d+)\s+months?\s+(?:later|after|credit|delay)",
    # Hindi: "दो महीने बाद"
    r"(" + _WORD_ALT + r"|\d+)\s+मह[ीि]ने?\s+बाद",
    # Awadhi: "दुई महीना बाद"
    r"(" + _WORD_ALT + r"|\d+)\s+महीना\s+बाद",
]


def _extract_payment_latency(text: str) -> Optional[int]:
    for pat in _LATENCY_DAY_RULES:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = _to_float(m.group(1))
            if val:
                return int(val)

    for pat in _LATENCY_MONTH_RULES:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            raw = m.group(1).strip()
            months: Optional[int] = int(raw) if raw.isdigit() else _WORD_TO_INT.get(raw)
            if months:
                return months * 30
    return None


# ── Loan amount ───────────────────────────────────────────────────────────────
# (pattern, multiply_by_lakh_directly)
_LOAN_RULES: list[tuple[str, bool]] = [
    # "a loan of 80,000" / "loan of ₹80,000"
    (r"(?:loan|उधार|ऋण)\s+of\s+(?:rs\.?\s*|₹\s*)?([\d][\d,]*(?:\.\d+)?)", False),
    # "need a loan of 80,000"
    (r"need\s+(?:a\s+)?(?:loan|credit)\s+(?:of\s+)?(?:rs\.?\s*|₹\s*)?([\d][\d,]*(?:\.\d+)?)", False),
    # "1 लाख का लोन" — number then lakh then loan keyword
    (r"([\d][\d,]*(?:\.\d+)?)\s*(?:लाख|lakh)\s+(?:का\s+)?(?:लोन|loan|उधार|ऋण)", True),
    # "50,000 रुपिया चाही" (Awadhi)
    (r"([\d][\d,]*(?:\.\d+)?)\s*(?:रुपिया|रुपये|rupees?)?\s*चाही", False),
    # "खरीदे बदे 50,000 रुपिया" (Awadhi: "to buy X rupees")
    (r"खरीदे\s+बदे\s+(?:rs\.?\s*|₹\s*)?([\d][\d,]*(?:\.\d+)?)", False),
    # Generic Hindi: "X रुपये का लोन"
    (r"([\d][\d,]*(?:\.\d+)?)\s*(?:रुपये|रुपिया)?\s*(?:का\s+)?(?:लोन|loan|उधार|ऋण)", False),
]


def _extract_loan_amount(text: str) -> Optional[float]:
    for pat, is_lakh in _LOAN_RULES:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = _to_float(m.group(1))
            if not val:
                continue
            if is_lakh:
                result = val * 1_00_000
                if result >= 1_000:
                    return result
                continue
            ctx = text[max(0, m.start(1) - 3): m.end(1) + 15]
            result = _expand_lakh(val, ctx)
            if result >= 1_000:
                return result
    return None


# ── Public API ────────────────────────────────────────────────────────────────

def parse_trade_statement(text: str) -> ParsedStatement:
    """
    Extract structured trade parameters from a free-form artisan statement.

    Handles English, Hindi, and Awadhi (and mixed inputs) via localized keyword
    matching and regex rules — no external API required.

    Parameters
    ----------
    text : str
        Raw conversational text in any supported language.

    Returns
    -------
    ParsedStatement  with None for any field that could not be reliably extracted.
    """
    return ParsedStatement(
        cluster              = _extract_cluster(text),
        monthly_turnover     = _extract_monthly_turnover(text),
        payment_latency_days = _extract_payment_latency(text),
        loan_amount          = _extract_loan_amount(text),
        raw_text             = text,
    )
