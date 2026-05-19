"""
PII Detection & Redaction — regex-based scanner for sensitive data.

Catches credit card numbers, SSNs, Aadhaar, PAN, bank accounts,
IFSC codes, phone numbers, email addresses, and SWIFT/BIC codes.

Important: financial amounts ($500, ₹450) and dates are NOT redacted.
"""

import re
from dataclasses import dataclass, field


@dataclass
class PIIResult:
    """Result of a PII redaction scan."""
    redacted_text: str = ""
    pii_found: bool = False
    detections: list = field(default_factory=list)   # e.g. ["credit_card", "email"]


# ── Pattern definitions ──────────────────────────────────────────
# Each tuple: (name, compiled regex, replacement string, group index to replace)
# group=0 means replace the full match; group=N means replace only capture group N.

_PII_PATTERNS: list[tuple[str, re.Pattern, str, int]] = [
    # ── Email ──
    (
        "email",
        re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
        "[EMAIL REDACTED]",
        0,
    ),

    # ── Bank account numbers — keyword + 8-18 digits ──
    # Must come before credit card so "account 12345678901234" isn't caught as card.
    (
        "bank_account",
        re.compile(r"(?i)(?:account|a/c|acct|acc)\s*(?:no|num|number|#)?[\s.:#\-]*(\d[\d\s\-]{6,17}\d)"),
        "[ACCOUNT REDACTED]",
        1,  # only replace the number part, keep the keyword
    ),

    # ── Credit / debit card numbers — 13-19 digits ──
    # Negative lookbehind for currency symbols so "$5000" isn't caught.
    (
        "credit_card",
        re.compile(
            r"(?<![₹$€£¥\d])"
            r"\b(?:\d[ \-]?){12,18}\d\b"
            r"(?!\d)"
        ),
        "[CARD REDACTED]",
        0,
    ),

    # ── Aadhaar (India) — 12 digits written as 4-4-4 with spaces ──
    (
        "aadhaar",
        re.compile(r"\b\d{4}\s\d{4}\s\d{4}\b"),
        "[AADHAAR REDACTED]",
        0,
    ),

    # ── SSN (US) — XXX-XX-XXXX ──
    (
        "ssn",
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "[SSN REDACTED]",
        0,
    ),

    # ── PAN (India) — 5 letters + 4 digits + 1 letter ──
    (
        "pan",
        re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
        "[PAN REDACTED]",
        0,
    ),

    # ── IFSC (India) — 4 letters + 0 + 6 alphanumeric ──
    (
        "ifsc",
        re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b"),
        "[IFSC REDACTED]",
        0,
    ),

    # ── SWIFT / BIC — 8 or 11 char bank code ──
    # Requires first 4 to be letters (bank), next 2 letters (country),
    # next 2 alphanumeric (location), optional 3 alphanumeric (branch).
    (
        "swift",
        re.compile(r"\b[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b"),
        "[SWIFT REDACTED]",
        0,
    ),

    # ── Phone numbers — optional +country, 10+ digits ──
    (
        "phone",
        re.compile(
            r"(?<![₹$€£¥\d])"
            r"(?:\+\d{1,3}[\s\-]?)"          # country code (required for safety)
            r"(?:\(?\d{2,5}\)?[\s\-]?)?"      # optional area code
            r"\d{3,5}[\s\-]?\d{3,5}"          # main number
            r"(?=\s|$|[.,;!?)])"
        ),
        "[PHONE REDACTED]",
        0,
    ),
]


class PIIRedactor:
    """Scans text for PII patterns and replaces them with safe placeholders."""

    def __init__(self):
        self.patterns = _PII_PATTERNS

    def redact(self, text: str) -> PIIResult:
        """Scan *text* for PII and return a redacted copy.

        Uses span-based collection: all patterns are matched against the
        original text first, then replacements are applied from right to left
        so earlier spans' positions aren't shifted.
        """
        # Collect all (start, end, replacement, pii_type) on the original text
        spans: list[tuple[int, int, str, str]] = []

        for pii_type, pattern, replacement, group_idx in self.patterns:
            for m in pattern.finditer(text):
                start = m.start(group_idx)
                end = m.end(group_idx)
                # Skip if this span overlaps with an already-found span
                if any(s <= start < e or s < end <= e for s, e, _, _ in spans):
                    continue
                spans.append((start, end, replacement, pii_type))

        if not spans:
            return PIIResult(redacted_text=text, pii_found=False)

        # Sort spans right-to-left so replacements don't shift indices
        spans.sort(key=lambda s: s[0], reverse=True)

        redacted = text
        detections: list[str] = []
        for start, end, replacement, pii_type in spans:
            redacted = redacted[:start] + replacement + redacted[end:]
            if pii_type not in detections:
                detections.append(pii_type)

        # Preserve original detection order (left-to-right)
        detections.reverse()

        return PIIResult(
            redacted_text=redacted,
            pii_found=True,
            detections=detections,
        )
