"""
Scope Enforcement — detects off-topic queries and redirects to finance.

Uses a keyword allowlist and off-topic patterns.  When unsure, errs on
the side of letting the message through (false positives are worse than
false negatives for user experience).
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ScopeResult:
    """Result of a scope check."""
    in_scope: bool = True
    canned_response: Optional[str] = None


# ── Canned redirect ─────────────────────────────────────────────
_REDIRECT = (
    "I'm your financial assistant — I can help with tracking expenses, "
    "managing budgets, and giving money advice. "
    "Try asking me something about your spending or savings!"
)

# ── Finance keyword allowlist ────────────────────────────────────
# If ANY of these appear in the message (case-insensitive), it's in scope.
# Includes English + common Hindi / Tamil / Spanish equivalents.
_FINANCE_KEYWORDS: set[str] = {
    # English — core
    "money", "spend", "spent", "spending", "budget", "expense", "expenses",
    "cost", "save", "saving", "savings", "income", "salary", "wage",
    "debt", "loan", "invest", "investing", "investment", "tax", "taxes",
    "bill", "bills", "payment", "pay", "paid", "rent", "mortgage",
    "credit", "debit", "bank", "finance", "financial", "afford",
    "cheap", "expensive", "price", "owe", "refund", "cashback",
    "emi", "interest", "insurance", "subscription", "tip", "tips",
    # English — categories & actions
    "grocery", "groceries", "food", "transport", "shopping",
    "entertainment", "health", "education", "utility", "utilities",
    "overspend", "overspent", "underspend", "balance", "total",
    "monthly", "weekly", "daily", "trend", "trends", "history",
    "category", "categories", "breakdown", "summary", "report",
    # English — bot interaction
    "thanks", "thank",
    # Hindi / Hinglish
    "paisa", "paise", "kharcha", "kharch", "bachat", "budget",
    "kamai", "kiraya", "karz", "udhar", "daam", "mehnga", "sasta",
    "bhugtan", "bhugtaan", "tankha", "tankhwah",
    # Tamil
    "panam", "selavu", "semipu", "varumaanam", "vaadagai", "kadan",
    "vilai", "mudhaleedu",
    # Spanish
    "dinero", "gastar", "gasto", "gastos", "presupuesto", "ahorro",
    "ahorrar", "ingreso", "sueldo", "deuda", "pagar", "precio",
    "alquiler", "factura",
}

# ── Off-topic patterns ───────────────────────────────────────────
# Clearly non-financial requests.  Each pattern is checked with re.search
# (case-insensitive).  Only high-confidence off-topic signals here.
_OFF_TOPIC_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"write (?:me )?(?:a |an )?(?:poem|essay|story|song|code|script|letter)",
        r"tell (?:me )?(?:a )?joke",
        r"(?:what(?:'s| is) the )?weather",
        r"who (?:is|was) (?:the )?(?:president|prime minister|king|queen|CEO)",
        r"help (?:me )?with (?:my )?(?:homework|assignment|exam|test|project)",
        r"play (?:a )?(?:game|music|song|video)",
        r"(?:what|who|where|when|how) (?:is|are|was|were|did) .{0,30}(?:capital|planet|country|continent|element|animal|species)",
        r"translate .{3,} (?:to|into) ",
        r"(?:recipe|cook|bake|roast|fry|grill) .{3,}",
        r"(?:relationship|dating|love|breakup|girlfriend|boyfriend|marriage) advice",
        r"(?:draw|paint|sketch|design) (?:me )?(?:a |an )?",
        r"(?:sing|rap|rhyme) (?:me )?(?:a |an )?",
        r"what(?:'s| is) (?:the )?meaning of life",
        r"(?:debug|compile|fix) (?:my |this |the )?(?:code|program|function|bug|error)",
    ]
]


class ScopeEnforcer:
    """Determines whether a user message is finance-related."""

    def __init__(self):
        self.finance_keywords = _FINANCE_KEYWORDS
        self.off_topic_patterns = _OFF_TOPIC_PATTERNS

    def is_in_scope(self, message: str) -> ScopeResult:
        """Check if *message* is within FinBot's financial scope.

        Decision logic (permissive by design):
          1. If ANY finance keyword is present → in scope (even if off-topic
             patterns also match — finance content takes priority).
          2. If the message is very short (≤3 words) → in scope (greetings,
             single-word queries — let the intent classifier handle it).
          3. If an off-topic pattern matches and NO finance keyword → out of scope.
          4. If unsure → in scope (false positives are worse than false negatives).
        """
        lower = message.lower()
        words = re.findall(r"[a-zA-Zऀ-ॿ஀-௿]+", lower)

        # Short messages always pass (greetings, "hi", "yes", etc.)
        if len(words) <= 3:
            return ScopeResult(in_scope=True)

        # Check for finance keywords — any hit means in scope
        for word in words:
            if word in self.finance_keywords:
                return ScopeResult(in_scope=True)

        # Check for off-topic patterns
        for pattern in self.off_topic_patterns:
            if pattern.search(lower):
                return ScopeResult(in_scope=False, canned_response=_REDIRECT)

        # Ambiguous — let it through
        return ScopeResult(in_scope=True)
