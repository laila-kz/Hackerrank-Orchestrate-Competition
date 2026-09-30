"""
Ticket Classification and Risk Assessment Module.

Provides deterministic risk evaluation, request type categorization,
and product area mapping across multi-domain support tickets.
"""

import re
from typing import ClassVar


class TicketClassifier:
    """Classifies support tickets and evaluates risk severity."""

    HIGH_RISK_KEYWORDS: ClassVar[tuple[str, ...]] = (
        "stolen", "fraud", "identity theft", "unauthorized", "compromised",
        "security vulnerability", "bug bounty", "police", "criminal",
        "hacked", "data breach", "lawsuit", "legal action",
    )

    OUT_OF_SCOPE_PATTERNS: ClassVar[tuple[str, ...]] = (
        r"who is", r"what is the name of", r"actor in", r"capital of", r"weather in",
        r"recipe for", r"tell me a joke", r"solve this math",
    )

    CONVERSATIONAL_INVALID: ClassVar[tuple[str, ...]] = (
        "hi", "hello", "hey", "thanks", "thank you", "bye", "goodbye",
        "awesome", "great", "ok", "okay", "test ticket",
    )

    @classmethod
    def evaluate_risk(cls, issue: str, subject: str = "") -> tuple[bool, str]:
        """
        Evaluate if a ticket contains high-risk or security-sensitive terms.
        
        Returns:
            Tuple[bool, str]: (is_high_risk, reason)
        """
        text = f"{issue} {subject}".lower()
        for kw in cls.HIGH_RISK_KEYWORDS:
            if kw in text:
                return True, f"High-risk security keyword detected: '{kw}'"
        return False, ""

    @classmethod
    def classify_request_type(cls, issue: str) -> str:
        """
        Determine the request type category.
        Allowed values: 'product_issue', 'feature_request', 'bug', 'invalid'
        """
        issue_lower = issue.strip().lower()

        # Check for conversational / out-of-scope invalid
        if cls.is_invalid_or_out_of_scope(issue_lower):
            return "invalid"

        # Bug signals
        if any(w in issue_lower for w in ["bug", "error", "failing", "not working", "crash", "site is down", "down", "404", "500"]):
            return "bug"

        # Feature request signals
        if any(w in issue_lower for w in ["feature", "suggest", "improvement", "wish list", "add support for", "would be great if"]):
            return "feature_request"

        return "product_issue"

    @classmethod
    def is_invalid_or_out_of_scope(cls, text: str) -> bool:
        """Check if query is general trivia, conversational, or out-of-scope."""
        text_clean = text.strip().lower()

        # Short conversational phrases
        words = text_clean.split()
        if len(words) <= 4 and any(phrase == text_clean or text_clean.startswith(phrase) for phrase in cls.CONVERSATIONAL_INVALID):
            return True

        # Out-of-scope trivia regex patterns
        for pattern in cls.OUT_OF_SCOPE_PATTERNS:
            if re.search(pattern, text_clean):
                return True

        return False

    @classmethod
    def extract_product_area(cls, text: str, default_company: str = "None") -> str:
        """Derive product area domain from ticket text and context."""
        t = text.lower()
        if any(w in t for w in ["login", "password", "sign in", "access", "seat", "permission", "account"]):
            return "account_access"
        elif any(w in t for w in ["billing", "payment", "invoice", "refund", "subscription", "charge"]):
            return "billing"
        elif any(w in t for w in ["test", "assessment", "challenge", "score", "reinvite", "time accommodation", "variant"]):
            return "screen" if default_company == "HackerRank" else "assessment"
        elif any(w in t for w in ["privacy", "delete account", "gdpr", "data", "conversation", "chat"]):
            return "privacy"
        elif any(w in t for w in ["api", "bedrock", "sdk", "rate limit", "endpoint", "key"]):
            return "api"
        elif any(w in t for w in ["card", "stolen", "fraud", "dispute", "transaction", "cheque"]):
            return "card_services" if "card" in t else "travel_support"
        elif any(w in t for w in ["down", "site is down", "outage"]):
            return "general_support"
        
        return "general_support"