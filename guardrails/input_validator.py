"""
Input Validator — prompt injection detection and profanity/abuse handling.

Injection detection uses regex pattern matching with a cumulative risk score.
Abuse handling uses severity levels so casual swearing isn't over-blocked.
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# ── Data classes ─────────────────────────────────────────────────

@dataclass
class InjectionResult:
    """Result of a prompt injection scan."""
    is_injection: bool = False
    risk_score: int = 0
    matched_patterns: list = None

    def __post_init__(self):
        if self.matched_patterns is None:
            self.matched_patterns = []


@dataclass
class AbuseResult:
    """Result of a profanity/abuse scan."""
    is_abusive: bool = False
    severity: str = "none"          # none | mild | moderate | severe
    canned_response: Optional[str] = None


# ── Injection canned response ───────────────────────────────────
# Friendly redirect — never reveals that injection was detected.
_INJECTION_RESPONSE = (
    "I can only help with financial topics like tracking expenses, "
    "budgets, and money advice. What would you like help with?"
)

# ── Injection patterns ───────────────────────────────────────────
# Each tuple: (compiled regex, risk weight, label for logging)
# Higher weight = stronger signal.  Total risk ≥ 4 → block.

_INJECTION_PATTERNS: list[tuple[re.Pattern, int, str]] = [
    # ── Instruction override ──
    (re.compile(r"ignore\s+(?:your\s+)?(?:all\s+|previous\s+|above\s+|prior\s+|any\s+)?(?:instructions|prompts|rules|guidelines|directions)", re.I), 3, "instruction_override"),
    (re.compile(r"disregard\s+(?:your\s+)?(?:all\s+|previous\s+|above\s+|prior\s+)?(?:instructions|prompts|rules)", re.I), 3, "instruction_override"),
    (re.compile(r"forget\s+(?:your\s+)?(?:all\s+|previous\s+|above\s+)?(?:instructions|prompts|rules|context)", re.I), 3, "instruction_override"),

    # ── Role hijacking ──
    (re.compile(r"you\s+are\s+now\b", re.I), 2, "role_hijack"),
    (re.compile(r"from\s+now\s+on\s+you\b", re.I), 2, "role_hijack"),
    (re.compile(r"pretend\s+(?:you\s+are|to\s+be)\b", re.I), 2, "role_hijack"),
    (re.compile(r"act\s+as\s+if\s+you\b", re.I), 2, "role_hijack"),
    (re.compile(r"respond\s+as\s+if\s+you\b", re.I), 2, "role_hijack"),
    (re.compile(r"you\s+(?:must|should|will)\s+now\s+(?:act|behave|respond)\b", re.I), 2, "role_hijack"),

    # ── Prompt / system extraction ──
    (re.compile(r"repeat\s+(?:your|the)\s+(?:system|initial|original|first)\s+(?:prompt|instructions|message)", re.I), 3, "prompt_extraction"),
    (re.compile(r"what\s+are\s+your\s+(?:instructions|rules|guidelines|prompts|directives)", re.I), 2, "prompt_extraction"),
    (re.compile(r"(?:show|reveal|display|output|print)\s+(?:me\s+)?(?:your|the)\s+(?:system|initial|original)\s+(?:prompt|instructions|message)", re.I), 3, "prompt_extraction"),
    (re.compile(r"tell\s+me\s+(?:your|the)\s+(?:system|initial|original)\s+(?:prompt|instructions|message)", re.I), 3, "prompt_extraction"),
    (re.compile(r"(?:what|how)\s+(?:is|was)\s+your\s+(?:system|initial)\s+prompt", re.I), 2, "prompt_extraction"),

    # ── Known jailbreak names ──
    (re.compile(r"\bDAN\b"), 2, "jailbreak_name"),
    (re.compile(r"Do\s+Anything\s+Now", re.I), 3, "jailbreak_name"),
    (re.compile(r"\bjailbreak\b", re.I), 2, "jailbreak_name"),
    (re.compile(r"\bdev(?:eloper)?\s+mode\b", re.I), 2, "jailbreak_name"),

    # ── Prompt template injection ──
    (re.compile(r"\[SYSTEM\]", re.I), 3, "template_injection"),
    (re.compile(r"\[INST\]", re.I), 3, "template_injection"),
    (re.compile(r"<<\s*SYS\s*>>", re.I), 3, "template_injection"),
    (re.compile(r"<\|(?:im_start|im_end|system|user|assistant)\|>", re.I), 3, "template_injection"),

    # ── Code execution / encoding tricks ──
    (re.compile(r"\bbase64\b", re.I), 1, "encoding_trick"),
    (re.compile(r"\bdecode\s+this\b", re.I), 1, "encoding_trick"),
    (re.compile(r"\beval\s*\(", re.I), 2, "code_exec"),
    (re.compile(r"\bexec\s*\(", re.I), 2, "code_exec"),

    # ── Secret extraction ──
    (re.compile(r"(?:what|show|tell|give)\s+(?:me\s+)?(?:your|the)\s+(?:api|secret|groq)\s*key", re.I), 3, "secret_extraction"),
    (re.compile(r"(?:what|show|tell)\s+(?:me\s+)?(?:your|the)\s+(?:env|environment)\s*(?:variable|var)?", re.I), 2, "secret_extraction"),

    # ── No-restrictions framing ──
    (re.compile(r"respond\s+(?:as\s+if|like)\s+you\s+have\s+no\s+(?:restrictions|limits|rules|boundaries)", re.I), 3, "no_restrictions"),
    (re.compile(r"without\s+(?:any\s+)?(?:restrictions|limits|rules|filters|guardrails|safety)", re.I), 2, "no_restrictions"),
]

# ── Suspicious structure thresholds ──────────────────────────────
_SUSPICIOUS_LENGTH = 500         # messages > 500 chars with instruction-like language
_INSTRUCTION_MARKERS = re.compile(
    r"(?:^|\n)\s*(?:\d+[\.\)]\s+|rule\s+\d+|step\s+\d+|instruction\s+\d+)",
    re.I | re.MULTILINE,
)

# Risk thresholds
_RISK_BLOCK = 4          # score ≥ 4 → block
_RISK_LOG_WARN = 2       # score ≥ 2 → log warning


class InputValidator:
    """Checks user messages for prompt injection attempts and abusive content."""

    def check_injection(self, message: str) -> InjectionResult:
        """Scan for prompt injection patterns.

        Scoring:
          - Each matched pattern adds its weight to the risk score.
          - Score < 2: clean (normal message that happens to contain a word)
          - Score 2-3: suspicious — allow but log a warning
          - Score ≥ 4: block with a friendly redirect
        """
        risk_score = 0
        matched: list[str] = []

        for pattern, weight, label in _INJECTION_PATTERNS:
            if pattern.search(message):
                risk_score += weight
                if label not in matched:
                    matched.append(label)

        # Suspicious structure check: long message with numbered instructions
        if len(message) > _SUSPICIOUS_LENGTH:
            markers = _INSTRUCTION_MARKERS.findall(message)
            if len(markers) >= 3:
                risk_score += 2
                matched.append("suspicious_structure")

        # Logging
        if risk_score >= _RISK_LOG_WARN:
            logger.warning(
                "Injection check: score=%d patterns=%s (blocked=%s)",
                risk_score, matched, risk_score >= _RISK_BLOCK,
            )

        is_blocked = risk_score >= _RISK_BLOCK
        return InjectionResult(
            is_injection=is_blocked,
            risk_score=risk_score,
            matched_patterns=matched,
        )

    def check_abuse(self, message: str) -> AbuseResult:
        """Scan for profanity and directed abuse."""
        # Placeholder — will be implemented in Task 6
        return AbuseResult()
