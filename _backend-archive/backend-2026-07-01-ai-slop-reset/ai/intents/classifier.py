"""
Intent recognition module.

Provides 3-tier intent classification:
    1. Regex pattern matching (fastest)
    2. Keyword matching (fast)
    3. LLM-based classification (most accurate)

Built-in intents cover common phone call scenarios for small businesses.

Usage:
    classifier = IntentClassifier()
    result = await classifier.classify("I'd like to book an appointment")
    print(result.intent, result.confidence)
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Pattern,
    Tuple,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Intent type definitions
# ---------------------------------------------------------------------------


class IntentType(str, Enum):
    """Built-in intent types for phone call scenarios."""

    SCHEDULE_APPOINTMENT = "schedule_appointment"
    TAKE_MESSAGE = "take_message"
    TRANSFER_CALL = "transfer_call"
    FAQ_ANSWER = "faq_answer"
    GET_HOURS = "get_hours"
    GET_PRICING = "get_pricing"
    SPEAK_HUMAN = "speak_human"
    CONFIRM = "confirm"
    DENY = "deny"
    GOODBYE = "goodbye"
    GREETING = "greeting"
    CANCEL_APPOINTMENT = "cancel_appointment"
    RESCHEDULE_APPOINTMENT = "reschedule_appointment"
    HOURS_INQUIRY = "hours_inquiry"
    PRICING_INQUIRY = "pricing_inquiry"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
#  Data models
# ---------------------------------------------------------------------------


@dataclass
class IntentResult:
    """Result of intent classification.

    Attributes:
        intent_type: Classified intent.
        confidence: Confidence score 0-100.
        method: Classification method used (regex/keyword/llm).
        entities: Extracted entities from the utterance.
        raw_text: Original input text.
    """

    intent_type: IntentType = IntentType.UNKNOWN
    confidence: int = 0
    method: str = ""
    entities: Dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""

    def is_confident(self, threshold: int = 70) -> bool:
        """Check if classification meets confidence threshold.

        Args:
            threshold: Minimum confidence required.

        Returns:
            True if confidence >= threshold.
        """
        return self.confidence >= threshold


# ---------------------------------------------------------------------------
#  Pattern definitions
# ---------------------------------------------------------------------------


class IntentPatterns:
    """Regex and keyword patterns for intent classification."""

    # Tier 1: High-confidence regex patterns
    REGEX_PATTERNS: Dict[IntentType, List[Pattern]] = {
        IntentType.SCHEDULE_APPOINTMENT: [
            re.compile(
                r"\b(book|schedule|make|set up)\s+(an?\s+)?(appointment|visit|consultation)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bI'd\s+like\s+to\s+(book|schedule|make)\b", re.IGNORECASE
            ),
            re.compile(
                r"\b(when|what\s+times?)\s+(are\s+you|do\s+you)\s+(available|open)\b",
                re.IGNORECASE,
            ),
        ],
        IntentType.TAKE_MESSAGE: [
            re.compile(
                r"\b(leave|take)\s+a?\s*(message|voicemail)\b", re.IGNORECASE
            ),
            re.compile(
                r"\bcan\s+(you|I)\s+(leave|send)\s+a?\s*message\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\btell\s+them\s+(that|to)\b", re.IGNORECASE
            ),
        ],
        IntentType.TRANSFER_CALL: [
            re.compile(
                r"\b(transfer|connect|redirect)\s+(me|this\s+call|the\s+call)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(can\s+I\s+speak\s+to|let\s+me\s+talk\s+to)\b",
                re.IGNORECASE,
            ),
        ],
        IntentType.SPEAK_HUMAN: [
            re.compile(
                r"\b(speak|talk)\s+to\s+a?\s*(human|person|real\s+person|someone|representative|agent)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(I\s+want|can\s+I\s+speak\s+to|get\s+me)\s+a?\s*(human|person|manager|supervisor)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\boperator\b", re.IGNORECASE
            ),
        ],
        IntentType.GOODBYE: [
            re.compile(
                r"\b(goodbye|bye|see\s+you|talk\s+to\s+you\s+later|have\s+a\s+good)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(that'?s\s+all|I'?m\s+done|that'?s\s+it|thank\s+you,?\s+bye)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(hang\s+up|end\s+(the\s+)?call)\b", re.IGNORECASE
            ),
        ],
        IntentType.GREETING: [
            re.compile(
                r"^(hello|hi|hey|good\s+(morning|afternoon|evening)|howdy)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(what'?s\s+up|how\s+are\s+you|how'?s\s+it\s+going)\b",
                re.IGNORECASE,
            ),
        ],
        IntentType.CONFIRM: [
            re.compile(
                r"\b(yes|yeah|yep|sure|absolutely|definitely|correct|right|exactly|of\s+course|that\s+works|okay|ok|sounds\s+good)\b",
                re.IGNORECASE,
            ),
        ],
        IntentType.DENY: [
            re.compile(
                r"\b(no|nope|nah|not\s+really|I\s+don't\s+think\s+so|no\s+thanks|no\s+thank\s+you)\b",
                re.IGNORECASE,
            ),
        ],
        IntentType.GET_HOURS: [
            re.compile(
                r"\b(what\s+(time|hours)\s+(do\s+you|are\s+you)\s+(open|close|available))\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(are\s+you\s+open|when\s+do\s+you\s+(open|close)|business\s+hours)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(what\s+days?\s+(are\s+you|do\s+you)\s+open)\b",
                re.IGNORECASE,
            ),
        ],
        IntentType.GET_PRICING: [
            re.compile(
                r"\b(how\s+much|what'?s?\s+the\s+(cost|price)|pricing|fee)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(what\s+do\s+you\s+charge|how\s+expensive|is\s+it\s+expensive)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(do\s+you\s+take\s+insurance|insurance|payment)\b",
                re.IGNORECASE,
            ),
        ],
        IntentType.FAQ_ANSWER: [
            re.compile(
                r"\b(what\s+(kind|types?)\s+of|do\s+you\s+offer|services?)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(where\s+are\s+you\s+located|address|directions)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(website|email|contact)\b", re.IGNORECASE
            ),
        ],
        IntentType.CANCEL_APPOINTMENT: [
            re.compile(
                r"\b(cancel|delete|remove)\s+(my\s+)?(appointment|booking)\b",
                re.IGNORECASE,
            ),
        ],
        IntentType.RESCHEDULE_APPOINTMENT: [
            re.compile(
                r"\b(reschedule|change|move|push|move)\s+(my\s+)?(appointment|booking)\b",
                re.IGNORECASE,
            ),
        ],
    }

    # Tier 2: Keyword patterns (fallback)
    KEYWORD_PATTERNS: Dict[IntentType, List[str]] = {
        IntentType.SCHEDULE_APPOINTMENT: [
            "appointment",
            "book",
            "schedule",
            "available",
            "slot",
            "time",
        ],
        IntentType.TAKE_MESSAGE: [
            "message",
            "voicemail",
            "callback",
            "call back",
            "tell them",
        ],
        IntentType.TRANSFER_CALL: [
            "transfer",
            "connect",
            "extension",
            "department",
        ],
        IntentType.SPEAK_HUMAN: [
            "human",
            "person",
            "real person",
            "representative",
            "agent",
            "manager",
            "supervisor",
            "operator",
        ],
        IntentType.GOODBYE: [
            "goodbye",
            "bye",
            "see you",
            "later",
            "hang up",
        ],
        IntentType.GREETING: [
            "hello",
            "hi",
            "hey",
            "good morning",
            "good afternoon",
        ],
        IntentType.CONFIRM: [
            "yes",
            "yeah",
            "sure",
            "okay",
            "ok",
            "correct",
        ],
        IntentType.DENY: [
            "no",
            "nope",
            "not",
            "don't",
        ],
        IntentType.GET_HOURS: [
            "hours",
            "open",
            "close",
            "time",
            "when",
            "today",
            "tomorrow",
        ],
        IntentType.GET_PRICING: [
            "price",
            "cost",
            "much",
            "expensive",
            "cheap",
            "afford",
            "insurance",
            "payment",
        ],
        IntentType.FAQ_ANSWER: [
            "what",
            "how",
            "where",
            "service",
            "offer",
            "do you",
            "location",
            "address",
        ],
    }


# ---------------------------------------------------------------------------
#  Entity extractor
# ---------------------------------------------------------------------------


class EntityExtractor:
    """Extract entities from user utterances."""

    # Time patterns
    TIME_PATTERN = re.compile(
        r"\b(\d{1,2}):(\d{2})\s*(am|pm|AM|PM)?\b|\b(\d{1,2})\s*(am|pm|noon|morning|afternoon|evening)\b"
    )

    # Date patterns
    DATE_PATTERN = re.compile(
        r"\b(today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        re.IGNORECASE,
    )

    # Phone number pattern
    PHONE_PATTERN = re.compile(
        r"\b(\d{3}[-.\s]?\d{3}[-.\s]?\d{4}|\(\d{3}\)\s*\d{3}[-.\s]?\d{4})\b"
    )

    # Name pattern (simplified)
    NAME_PATTERN = re.compile(
        r"\b(my\s+name\s+is|this\s+is|I'?m)\s+([A-Za-z\s]+)", re.IGNORECASE
    )

    @classmethod
    def extract(
        cls, text: str, intent: IntentType
    ) -> Dict[str, Any]:
        """Extract entities relevant to the detected intent.

        Args:
            text: User utterance.
            intent: Detected intent.

        Returns:
            Dict of extracted entities.
        """
        entities: Dict[str, Any] = {}

        # Extract time mentions
        times = cls.TIME_PATTERN.findall(text)
        if times:
            entities["times"] = [t[0] or t[3] for t in times if t[0] or t[3]]

        # Extract date mentions
        dates = cls.DATE_PATTERN.findall(text)
        if dates:
            entities["dates"] = dates

        # Extract phone numbers
        phones = cls.PHONE_PATTERN.findall(text)
        if phones:
            entities["phone_numbers"] = phones

        # Extract names
        names = cls.NAME_PATTERN.findall(text)
        if names:
            entities["names"] = [n[1].strip() for n in names]

        # Intent-specific extraction
        if intent == IntentType.SCHEDULE_APPOINTMENT:
            service_match = re.search(
                r"\b(for|a|an)\s+([a-z\s]+)(appointment|visit|consultation)?",
                text,
                re.IGNORECASE,
            )
            if service_match:
                entities["service"] = service_match.group(2).strip()

        elif intent == IntentType.TAKE_MESSAGE:
            entities["message"] = text

        return entities


# ---------------------------------------------------------------------------
#  Main classifier
# ---------------------------------------------------------------------------


class IntentClassifier:
    """3-tier intent classifier for phone conversation utterances.

    Classification pipeline:
        1. Regex matching (highest confidence, fastest)
        2. Keyword matching (medium confidence)
        3. LLM fallback (lowest confidence, most flexible)

    Args:
        llm_client: Optional LLM client for tier-3 classification.
        regex_confidence: Confidence score for regex matches.
        keyword_confidence: Confidence score for keyword matches.
        llm_confidence: Confidence score for LLM matches.
    """

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        regex_confidence: int = 95,
        keyword_confidence: int = 75,
        llm_confidence: int = 85,
    ) -> None:
        self._llm = llm_client
        self.regex_confidence = regex_confidence
        self.keyword_confidence = keyword_confidence
        self.llm_confidence = llm_confidence
        self._patterns = IntentPatterns()
        self._extractor = EntityExtractor()
        self._call_count: int = 0
        self._regex_hits: int = 0
        self._keyword_hits: int = 0
        self._llm_hits: int = 0

    # ------------------------------------------------------------------ #
    #  Tier 1: Regex classification
    # ------------------------------------------------------------------ #

    def _classify_regex(self, text: str) -> Optional[IntentResult]:
        """Classify using regex patterns (Tier 1).

        Args:
            text: Input text.

        Returns:
            IntentResult if matched, None otherwise.
        """
        text_lower = text.lower().strip()

        # Short utterances - check confirm/deny/goodbye first
        if len(text_lower.split()) <= 3:
            for intent, patterns in self._patterns.REGEX_PATTERNS.items():
                if intent in (IntentType.CONFIRM, IntentType.DENY, IntentType.GOODBYE):
                    for pattern in patterns:
                        if pattern.search(text):
                            return IntentResult(
                                intent_type=intent,
                                confidence=self.regex_confidence,
                                method="regex",
                                raw_text=text,
                            )

        # Full regex scan
        for intent, patterns in self._patterns.REGEX_PATTERNS.items():
            for pattern in patterns:
                if pattern.search(text):
                    entities = self._extractor.extract(text, intent)
                    return IntentResult(
                        intent_type=intent,
                        confidence=self.regex_confidence,
                        method="regex",
                        entities=entities,
                        raw_text=text,
                    )

        return None

    # ------------------------------------------------------------------ #
    #  Tier 2: Keyword classification
    # ------------------------------------------------------------------ #

    def _classify_keyword(self, text: str) -> Optional[IntentResult]:
        """Classify using keyword patterns (Tier 2).

        Args:
            text: Input text.

        Returns:
            IntentResult if matched, None otherwise.
        """
        text_lower = text.lower()
        words = set(text_lower.split())
        best_intent: Optional[IntentType] = None
        best_score: float = 0.0

        for intent, keywords in self._patterns.KEYWORD_PATTERNS.items():
            score = 0.0
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    # Longer keyword matches = higher confidence
                    score += len(keyword) / len(text_lower)
                elif any(kw in words for kw in keyword.lower().split()):
                    score += 0.5 * len(keyword) / len(text_lower)

            if score > best_score:
                best_score = score
                best_intent = intent

        if best_intent and best_score > 0.1:
            # Scale confidence by match quality
            confidence = min(
                self.keyword_confidence,
                int(self.keyword_confidence * min(best_score * 5, 1.0)),
            )
            entities = self._extractor.extract(text, best_intent)
            return IntentResult(
                intent_type=best_intent,
                confidence=max(confidence, 50),
                method="keyword",
                entities=entities,
                raw_text=text,
            )

        return None

    # ------------------------------------------------------------------ #
    #  Tier 3: LLM classification
    # ------------------------------------------------------------------ #

    async def _classify_llm(self, text: str) -> Optional[IntentResult]:
        """Classify using LLM (Tier 3, fallback).

        Args:
            text: Input text.

        Returns:
            IntentResult if classified, None if LLM unavailable.
        """
        if self._llm is None:
            return None

        try:
            intent_list = "\n".join(
                f"- {it.value}" for it in IntentType if it != IntentType.UNKNOWN
            )

            prompt = (
                f"Classify the following phone call utterance into one of these intents:\n"
                f"{intent_list}\n"
                f"\nUtterance: \"{text}\"\n"
                f"\nRespond with ONLY the intent name, nothing else."
            )

            response = await self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=32,
                temperature=0.0,
            )

            intent_text = response.content.strip().lower().replace(" ", "_")

            # Map response to known intent
            for intent in IntentType:
                if intent.value.lower() in intent_text:
                    entities = self._extractor.extract(text, intent)
                    return IntentResult(
                        intent_type=intent,
                        confidence=self.llm_confidence,
                        method="llm",
                        entities=entities,
                        raw_text=text,
                    )

            return None

        except Exception as exc:
            logger.warning(f"LLM classification failed: {exc}")
            return None

    # ------------------------------------------------------------------ #
    #  Main classify method
    # ------------------------------------------------------------------ #

    async def classify(self, text: str) -> IntentResult:
        """Classify user utterance into an intent.

        Runs the 3-tier classification pipeline and returns the best result.

        Args:
            text: User utterance text.

        Returns:
            IntentResult with intent type and confidence.
        """
        if not text or not text.strip():
            return IntentResult(
                intent_type=IntentType.UNKNOWN,
                confidence=0,
                method="none",
                raw_text=text,
            )

        self._call_count += 1

        # Tier 1: Regex
        result = self._classify_regex(text)
        if result:
            self._regex_hits += 1
            logger.debug(
                f"Intent (regex): {result.intent_type.value} "
                f"({result.confidence}%): {text[:50]}"
            )
            return result

        # Tier 2: Keyword
        result = self._classify_keyword(text)
        if result:
            self._keyword_hits += 1
            logger.debug(
                f"Intent (keyword): {result.intent_type.value} "
                f"({result.confidence}%): {text[:50]}"
            )
            return result

        # Tier 3: LLM fallback
        result = await self._classify_llm(text)
        if result:
            self._llm_hits += 1
            logger.debug(
                f"Intent (llm): {result.intent_type.value} "
                f"({result.confidence}%): {text[:50]}"
            )
            return result

        # Default to unknown
        logger.debug(f"Intent: unknown for: {text[:50]}")
        return IntentResult(
            intent_type=IntentType.UNKNOWN,
            confidence=30,
            method="fallback",
            raw_text=text,
        )

    def classify_sync(self, text: str) -> IntentResult:
        """Synchronous classification (tiers 1-2 only).

        Args:
            text: User utterance text.

        Returns:
            IntentResult from regex or keyword classification.
        """
        if not text or not text.strip():
            return IntentResult(
                intent_type=IntentType.UNKNOWN,
                confidence=0,
                method="none",
                raw_text=text,
            )

        self._call_count += 1

        result = self._classify_regex(text)
        if result:
            self._regex_hits += 1
            return result

        result = self._classify_keyword(text)
        if result:
            self._keyword_hits += 1
            return result

        return IntentResult(
            intent_type=IntentType.UNKNOWN,
            confidence=30,
            method="fallback",
            raw_text=text,
        )

    # ------------------------------------------------------------------ #
    #  Utility methods
    # ------------------------------------------------------------------ #

    def get_stats(self) -> Dict[str, Any]:
        """Get classification statistics.

        Returns:
            Dict with classification metrics.
        """
        if self._call_count == 0:
            return {
                "total": 0,
                "regex_hits": 0,
                "keyword_hits": 0,
                "llm_hits": 0,
                "regex_rate": 0.0,
                "keyword_rate": 0.0,
                "llm_rate": 0.0,
            }

        return {
            "total": self._call_count,
            "regex_hits": self._regex_hits,
            "keyword_hits": self._keyword_hits,
            "llm_hits": self._llm_hits,
            "regex_rate": self._regex_hits / self._call_count,
            "keyword_rate": self._keyword_hits / self._call_count,
            "llm_rate": self._llm_hits / self._call_count,
        }

    def reset_stats(self) -> None:
        """Reset classification statistics."""
        self._call_count = 0
        self._regex_hits = 0
        self._keyword_hits = 0
        self._llm_hits = 0


# ---------------------------------------------------------------------------
#  Factory function
# ---------------------------------------------------------------------------

_intent_classifier_instance: Optional[IntentClassifier] = None


async def get_intent_classifier(
    llm_client: Optional[Any] = None,
) -> IntentClassifier:
    """Get or create singleton IntentClassifier instance.

    Args:
        llm_client: Optional LLM client for tier-3 classification.

    Returns:
        Configured IntentClassifier.
    """
    global _intent_classifier_instance
    if _intent_classifier_instance is None:
        _intent_classifier_instance = IntentClassifier(llm_client=llm_client)
    return _intent_classifier_instance
