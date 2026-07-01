"""Owlbell product module catalog."""

from __future__ import annotations


def list_modules() -> list[dict]:
    return [
        {
            "key": "ai_call_capture",
            "name": "AI Call Capture",
            "priority": 1,
            "description": "Answer calls, qualify jobs, summarize details, and alert the owner.",
        },
        {
            "key": "missed_call_text_back",
            "name": "Missed-Call Text-Back",
            "priority": 1,
            "description": "Text missed callers immediately and capture the opportunity.",
        },
        {
            "key": "weekly_ops_report",
            "name": "Weekly Ops Report",
            "priority": 1,
            "description": "Report calls, missed leads, quote follow-up, reviews, and revenue leakage.",
        },
        {
            "key": "quote_follow_up",
            "name": "Quote Follow-Up",
            "priority": 2,
            "description": "Follow up open estimates until they convert, decline, or need owner action.",
        },
        {
            "key": "review_requests",
            "name": "Review Requests",
            "priority": 2,
            "description": "Request reviews from satisfied customers and route negative feedback privately.",
        },
        {
            "key": "customer_reactivation",
            "name": "Customer Reactivation",
            "priority": 3,
            "description": "Re-engage previous customers for seasonal and maintenance work.",
        },
    ]
