"""Tests for the Signal Detection Agent.

These exercise the deterministic core (no network, no LLM) — review-text
mining, after-hours gap detection, scoring, and the write-back of triggers
into intelligence observations.
"""

from __future__ import annotations

from backend.leads.agents.signals import SignalAgent, _categorise_review


def _review(text: str, rating: int = 1) -> dict:
    return {"text": text, "rating": rating, "time": 0}


class TestReviewCategorisation:
    def test_voicemail_complaint(self):
        assert "voicemail" in _categorise_review("Called twice, both times went to voicemail.")

    def test_no_answer_complaint(self):
        assert "no_answer" in _categorise_review("Phone just rings, nobody ever answers.")

    def test_callback_complaint(self):
        assert "callback" in _categorise_review("They never called me back after I left a message.")

    def test_slow_response_complaint(self):
        assert "slow_response" in _categorise_review("Very unresponsive, took days to hear anything.")

    def test_happy_review_has_no_signal(self):
        assert _categorise_review("Fantastic service, fixed my AC same day. Highly recommend!") == []

    def test_empty_text(self):
        assert _categorise_review("") == []


class TestMissedCallRisk:
    def test_risk_rises_with_complaint_ratio(self):
        lead = {
            "name": "Acme Plumbing",
            "rating": 3.5,
            "reviews": [
                _review("Could never reach them, phone goes to voicemail."),
                _review("Never called me back. Had to hire someone else."),
                _review("Great work once they showed up."),
            ],
        }
        signals = SignalAgent().detect(lead)
        assert signals["review_signals"]["responsiveness_complaints"] == 2
        assert signals["review_signals"]["reviews_analyzed"] == 3
        assert signals["missed_call_risk"] > 0.5
        assert signals["has_fresh_trigger"] is True

    def test_no_reviews_means_zero_review_risk(self):
        signals = SignalAgent().detect({"name": "X", "reviews": []})
        assert signals["missed_call_risk"] == 0.0
        assert signals["review_signals"]["reviews_analyzed"] == 0

    def test_clean_reviews_no_trigger(self):
        lead = {
            "name": "Best HVAC",
            "rating": 4.9,
            "reviews": [_review("Prompt, professional, answered right away.", rating=5)],
            "_intelligence": {"has_online_booking": True, "phone_prominence": "footer_only"},
        }
        signals = SignalAgent().detect(lead)
        assert signals["missed_call_risk"] == 0.0
        assert signals["triggers"] == []


class TestAfterHoursGap:
    def test_emergency_claim_with_limited_hours_is_a_gap(self):
        lead = {
            "name": "24/7 Emergency Plumbers",
            "_intelligence": {"has_emergency_service": True},
            "opening_hours": {
                "weekday_text": [
                    "Monday: 8:00 AM – 5:00 PM",
                    "Saturday: Closed",
                    "Sunday: Closed",
                ]
            },
        }
        signals = SignalAgent().detect(lead)
        assert signals["after_hours_gap"] is True
        assert any("after-hours" in t for t in signals["triggers"])

    def test_genuinely_24h_business_has_no_gap(self):
        lead = {
            "name": "Always Open HVAC",
            "_intelligence": {"has_emergency_service": True},
            "opening_hours": {"weekday_text": ["Monday: Open 24 hours", "Tuesday: Open 24 hours"]},
        }
        signals = SignalAgent().detect(lead)
        assert signals["after_hours_gap"] is False

    def test_no_emergency_claim_no_gap(self):
        lead = {
            "name": "9-5 Painters",
            "_intelligence": {"has_emergency_service": False},
            "opening_hours": {"weekday_text": ["Monday: 9:00 AM – 5:00 PM"]},
        }
        assert SignalAgent().detect(lead)["after_hours_gap"] is False


class TestEnrichment:
    def test_triggers_folded_into_observations(self):
        lead = {
            "name": "Acme",
            "rating": 3.0,
            "reviews": [_review("Goes straight to voicemail every time.")],
            "_intelligence": {"observations": "Basic site."},
        }
        enriched = SignalAgent().detect_and_enrich(lead)
        assert "_signals" in enriched
        assert "SIGNALS:" in enriched["_intelligence"]["observations"]
        assert "Basic site." in enriched["_intelligence"]["observations"]
        assert enriched["_missed_call_risk"] == enriched["_signals"]["missed_call_risk"]

    def test_enrich_without_intelligence_does_not_crash(self):
        lead = {"name": "NoIntel", "reviews": [_review("never answer the phone")]}
        enriched = SignalAgent().detect_and_enrich(lead)
        assert enriched["_signals"]["has_fresh_trigger"] is True

    def test_detect_many_preserves_order_and_count(self):
        leads = [
            {"name": "A", "reviews": [_review("voicemail every time")]},
            {"name": "B", "reviews": [_review("great service")]},
        ]
        out = SignalAgent().detect_many(leads)
        assert [l["name"] for l in out] == ["A", "B"]
        assert out[0]["_signals"]["has_fresh_trigger"] is True
        assert out[1]["_signals"]["has_fresh_trigger"] is False
