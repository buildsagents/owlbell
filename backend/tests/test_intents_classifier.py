"""
Tests for Intent Classifier.

Covers 3-tier classification, all built-in intents, confidence scoring,
entity extraction, and statistics.
"""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import AsyncMock

import pytest

from backend.ai.intents.classifier import (
    EntityExtractor,
    IntentClassifier,
    IntentPatterns,
    IntentResult,
    IntentType,
    get_intent_classifier,
)


# ---------------------------------------------------------------------------
#  IntentResult tests
# ---------------------------------------------------------------------------


class TestIntentResult:
    """Tests for IntentResult dataclass."""

    def test_basic_creation(self) -> None:
        """Test creating a result."""
        result = IntentResult(
            intent_type=IntentType.GREETING,
            confidence=95,
            method="regex",
        )
        assert result.intent_type == IntentType.GREETING
        assert result.confidence == 95
        assert result.method == "regex"

    def test_is_confident_above_threshold(self) -> None:
        """Test confidence above threshold."""
        result = IntentResult(confidence=80)
        assert result.is_confident(threshold=70)

    def test_is_confident_below_threshold(self) -> None:
        """Test confidence below threshold."""
        result = IntentResult(confidence=50)
        assert not result.is_confident(threshold=70)

    def test_defaults(self) -> None:
        """Test default values."""
        result = IntentResult()
        assert result.intent_type == IntentType.UNKNOWN
        assert result.confidence == 0
        assert result.entities == {}


# ---------------------------------------------------------------------------
#  IntentPatterns tests
# ---------------------------------------------------------------------------


class TestIntentPatterns:
    """Tests for IntentPatterns."""

    def test_regex_patterns_defined(self) -> None:
        """Test that regex patterns are defined for all major intents."""
        assert IntentType.SCHEDULE_APPOINTMENT in IntentPatterns.REGEX_PATTERNS
        assert IntentType.SPEAK_HUMAN in IntentPatterns.REGEX_PATTERNS
        assert IntentType.GOODBYE in IntentPatterns.REGEX_PATTERNS
        assert IntentType.GREETING in IntentPatterns.REGEX_PATTERNS

    def test_keyword_patterns_defined(self) -> None:
        """Test keyword patterns."""
        assert IntentType.SCHEDULE_APPOINTMENT in IntentPatterns.KEYWORD_PATTERNS
        assert IntentType.GET_HOURS in IntentPatterns.KEYWORD_PATTERNS
        assert IntentType.GET_PRICING in IntentPatterns.KEYWORD_PATTERNS

    def test_regex_patterns_are_valid(self) -> None:
        """Test that all regex patterns compile."""
        import re

        for intent, patterns in IntentPatterns.REGEX_PATTERNS.items():
            for pattern in patterns:
                assert isinstance(pattern, re.Pattern)


# ---------------------------------------------------------------------------
#  EntityExtractor tests
# ---------------------------------------------------------------------------


class TestEntityExtractor:
    """Tests for EntityExtractor."""

    def test_extract_times(self) -> None:
        """Test time extraction."""
        entities = EntityExtractor.extract(
            "I want to come at 3:00 pm", IntentType.SCHEDULE_APPOINTMENT
        )
        assert "times" in entities

    def test_extract_dates(self) -> None:
        """Test date extraction."""
        entities = EntityExtractor.extract(
            "I want to come tomorrow", IntentType.SCHEDULE_APPOINTMENT
        )
        assert "dates" in entities
        assert "tomorrow" in [d.lower() for d in entities["dates"]]

    def test_extract_phone_numbers(self) -> None:
        """Test phone number extraction."""
        entities = EntityExtractor.extract(
            "My number is 555-123-4567", IntentType.TAKE_MESSAGE
        )
        assert "phone_numbers" in entities

    def test_extract_names(self) -> None:
        """Test name extraction."""
        entities = EntityExtractor.extract(
            "My name is John Smith", IntentType.GREETING
        )
        assert "names" in entities

    def test_appointment_service(self) -> None:
        """Test service extraction for appointments."""
        entities = EntityExtractor.extract(
            "Book an appointment for a haircut", IntentType.SCHEDULE_APPOINTMENT
        )
        assert "service" in entities

    def test_no_entities(self) -> None:
        """Test text with no extractable entities."""
        entities = EntityExtractor.extract("Hello", IntentType.GREETING)
        assert isinstance(entities, dict)


# ---------------------------------------------------------------------------
#  IntentClassifier - Tier 1 (Regex) tests
# ---------------------------------------------------------------------------


class TestRegexClassification:
    """Tests for Tier 1 regex classification."""

    @pytest.fixture
    def classifier(self) -> IntentClassifier:
        return IntentClassifier()

    def test_schedule_appointment(self, classifier: IntentClassifier) -> None:
        """Test scheduling appointment intent."""
        result = classifier._classify_regex("I'd like to book an appointment")
        assert result is not None
        assert result.intent_type == IntentType.SCHEDULE_APPOINTMENT

    def test_take_message(self, classifier: IntentClassifier) -> None:
        """Test take message intent."""
        result = classifier._classify_regex("Can I leave a message?")
        assert result is not None
        assert result.intent_type == IntentType.TAKE_MESSAGE

    def test_transfer_call(self, classifier: IntentClassifier) -> None:
        """Test transfer call intent."""
        result = classifier._classify_regex("Please transfer me to billing")
        assert result is not None
        assert result.intent_type == IntentType.TRANSFER_CALL

    def test_speak_human(self, classifier: IntentClassifier) -> None:
        """Test speak to human intent."""
        result = classifier._classify_regex("I want to speak to a human")
        assert result is not None
        assert result.intent_type == IntentType.SPEAK_HUMAN

    def test_goodbye(self, classifier: IntentClassifier) -> None:
        """Test goodbye intent."""
        result = classifier._classify_regex("Goodbye, thanks for your help")
        assert result is not None
        assert result.intent_type == IntentType.GOODBYE

    def test_greeting(self, classifier: IntentClassifier) -> None:
        """Test greeting intent."""
        result = classifier._classify_regex("Hello there")
        assert result is not None
        assert result.intent_type == IntentType.GREETING

    def test_confirm(self, classifier: IntentClassifier) -> None:
        """Test confirm intent."""
        result = classifier._classify_regex("Yes, that works for me")
        assert result is not None
        assert result.intent_type == IntentType.CONFIRM

    def test_deny(self, classifier: IntentClassifier) -> None:
        """Test deny intent."""
        result = classifier._classify_regex("No, that's not right")
        assert result is not None
        assert result.intent_type == IntentType.DENY

    def test_get_hours(self, classifier: IntentClassifier) -> None:
        """Test hours inquiry intent."""
        result = classifier._classify_regex("What time do you open?")
        assert result is not None
        assert result.intent_type == IntentType.GET_HOURS

    def test_get_pricing(self, classifier: IntentClassifier) -> None:
        """Test pricing inquiry intent."""
        result = classifier._classify_regex("How much does it cost?")
        assert result is not None
        assert result.intent_type == IntentType.GET_PRICING

    def test_faq_answer(self, classifier: IntentClassifier) -> None:
        """Test FAQ intent."""
        result = classifier._classify_regex("What services do you offer?")
        assert result is not None
        assert result.intent_type == IntentType.FAQ_ANSWER

    def test_cancel_appointment(self, classifier: IntentClassifier) -> None:
        """Test cancel appointment intent."""
        result = classifier._classify_regex("I need to cancel my appointment")
        assert result is not None
        assert result.intent_type == IntentType.CANCEL_APPOINTMENT

    def test_reschedule_appointment(self, classifier: IntentClassifier) -> None:
        """Test reschedule intent."""
        result = classifier._classify_regex("Can I reschedule my booking?")
        assert result is not None
        assert result.intent_type == IntentType.RESCHEDULE_APPOINTMENT

    def test_short_confirm(self, classifier: IntentClassifier) -> None:
        """Test short confirm utterance."""
        result = classifier._classify_regex("yes")
        assert result is not None
        assert result.intent_type == IntentType.CONFIRM

    def test_short_deny(self, classifier: IntentClassifier) -> None:
        """Test short deny utterance."""
        result = classifier._classify_regex("no")
        assert result is not None
        assert result.intent_type == IntentType.DENY

    def test_no_match_returns_none(self, classifier: IntentClassifier) -> None:
        """Test that unmatched text returns None."""
        result = classifier._classify_regex("xyz abc 123 unknown")
        assert result is None


# ---------------------------------------------------------------------------
#  IntentClassifier - Tier 2 (Keyword) tests
# ---------------------------------------------------------------------------


class TestKeywordClassification:
    """Tests for Tier 2 keyword classification."""

    @pytest.fixture
    def classifier(self) -> IntentClassifier:
        return IntentClassifier()

    def test_appointment_keyword(self, classifier: IntentClassifier) -> None:
        """Test keyword detection for appointment."""
        result = classifier._classify_keyword("I want appointment please")
        assert result is not None
        assert result.intent_type == IntentType.SCHEDULE_APPOINTMENT

    def test_human_keyword(self, classifier: IntentClassifier) -> None:
        """Test keyword detection for human."""
        result = classifier._classify_keyword("give me human operator")
        assert result is not None
        assert result.intent_type == IntentType.SPEAK_HUMAN

    def test_hours_keyword(self, classifier: IntentClassifier) -> None:
        """Test keyword detection for hours."""
        result = classifier._classify_keyword("what are your hours today")
        assert result is not None
        assert result.intent_type == IntentType.GET_HOURS

    def test_price_keyword(self, classifier: IntentClassifier) -> None:
        """Test keyword detection for pricing."""
        result = classifier._classify_keyword("how much does it cost")
        assert result is not None
        assert result.intent_type == IntentType.GET_PRICING

    def test_unknown_text(self, classifier: IntentClassifier) -> None:
        """Test text with no known keywords."""
        result = classifier._classify_keyword("xyz qwerty 12345")
        assert result is None

    def test_keyword_confidence(self, classifier: IntentClassifier) -> None:
        """Test keyword confidence scoring."""
        result = classifier._classify_keyword("book appointment schedule")
        assert result is not None
        assert result.confidence > 0


# ---------------------------------------------------------------------------
#  IntentClassifier - Main classify tests
# ---------------------------------------------------------------------------


class TestMainClassify:
    """Tests for the main classify method."""

    @pytest.fixture
    def classifier(self) -> IntentClassifier:
        return IntentClassifier()

    @pytest.mark.asyncio
    async def test_classify_greeting(self, classifier: IntentClassifier) -> None:
        """Test classifying a greeting."""
        result = await classifier.classify("Hello, how are you?")
        assert result.intent_type == IntentType.GREETING
        assert result.confidence > 0
        assert result.method == "regex"

    @pytest.mark.asyncio
    async def test_classify_appointment(self, classifier: IntentClassifier) -> None:
        """Test classifying appointment request."""
        result = await classifier.classify("I want to book an appointment")
        assert result.intent_type == IntentType.SCHEDULE_APPOINTMENT

    @pytest.mark.asyncio
    async def test_classify_human_request(self, classifier: IntentClassifier) -> None:
        """Test classifying human transfer request."""
        result = await classifier.classify("I want to speak to a human")
        assert result.intent_type == IntentType.SPEAK_HUMAN

    @pytest.mark.asyncio
    async def test_classify_goodbye(self, classifier: IntentClassifier) -> None:
        """Test classifying goodbye."""
        result = await classifier.classify("Goodbye, have a nice day")
        assert result.intent_type == IntentType.GOODBYE

    @pytest.mark.asyncio
    async def test_classify_confirm(self, classifier: IntentClassifier) -> None:
        """Test classifying confirmation."""
        result = await classifier.classify("Yes, that sounds good")
        assert result.intent_type == IntentType.CONFIRM

    @pytest.mark.asyncio
    async def test_classify_deny(self, classifier: IntentClassifier) -> None:
        """Test classifying denial."""
        result = await classifier.classify("No thank you")
        assert result.intent_type == IntentType.DENY

    @pytest.mark.asyncio
    async def test_classify_empty(self, classifier: IntentClassifier) -> None:
        """Test classifying empty text."""
        result = await classifier.classify("")
        assert result.intent_type == IntentType.UNKNOWN
        assert result.confidence == 0

    @pytest.mark.asyncio
    async def test_classify_whitespace(self, classifier: IntentClassifier) -> None:
        """Test classifying whitespace."""
        result = await classifier.classify("   ")
        assert result.intent_type == IntentType.UNKNOWN

    def test_classify_sync(self, classifier: IntentClassifier) -> None:
        """Test synchronous classification."""
        result = classifier.classify_sync("Hello")
        assert result.intent_type == IntentType.GREETING
        assert result.method == "regex"

    def test_classify_sync_keyword_fallback(
        self, classifier: IntentClassifier
    ) -> None:
        """Test sync falls back to keywords."""
        # Text that doesn't match regex but matches keywords
        result = classifier.classify_sync("i really need a human person now")
        assert result is not None
        assert result.confidence > 0


# ---------------------------------------------------------------------------
#  Statistics tests
# ---------------------------------------------------------------------------


class TestStatistics:
    """Tests for classification statistics."""

    @pytest.fixture
    def classifier(self) -> IntentClassifier:
        return IntentClassifier()

    def test_initial_stats(self, classifier: IntentClassifier) -> None:
        """Test initial stats are zero."""
        stats = classifier.get_stats()
        assert stats["total"] == 0
        assert stats["regex_hits"] == 0

    def test_stats_after_classification(
        self, classifier: IntentClassifier
    ) -> None:
        """Test stats after some classifications."""
        classifier.classify_sync("Hello")
        classifier.classify_sync("Goodbye")
        classifier.classify_sync("Yes")

        stats = classifier.get_stats()
        assert stats["total"] == 3
        assert stats["regex_hits"] == 3
        assert stats["regex_rate"] == 1.0

    def test_reset_stats(self, classifier: IntentClassifier) -> None:
        """Test stats reset."""
        classifier.classify_sync("Hello")
        classifier.reset_stats()
        stats = classifier.get_stats()
        assert stats["total"] == 0


# ---------------------------------------------------------------------------
#  Factory tests
# ---------------------------------------------------------------------------


class TestFactory:
    """Tests for factory function."""

    @pytest.mark.asyncio
    async def test_get_intent_classifier(self) -> None:
        """Test getting classifier instance."""
        classifier = await get_intent_classifier()
        assert isinstance(classifier, IntentClassifier)

    @pytest.mark.asyncio
    async def test_singleton(self) -> None:
        """Test that factory returns same instance."""
        c1 = await get_intent_classifier()
        c2 = await get_intent_classifier()
        assert c1 is c2

    @pytest.mark.asyncio
    async def test_with_llm_client(self) -> None:
        """Test getting classifier with LLM client."""
        mock_llm = AsyncMock()
        classifier = await get_intent_classifier(llm_client=mock_llm)
        assert classifier._llm is mock_llm
