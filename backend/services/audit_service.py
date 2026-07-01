"""Audit generation service.

This intentionally returns deterministic starter findings. Replace this with
real website/review enrichment once the sales funnel is rebuilt.
"""

from __future__ import annotations

from uuid import uuid4

from backend.schemas.audit import AuditLeak, AuditRequest, AuditResponse


def create_audit(payload: AuditRequest) -> AuditResponse:
    leaks = [
        AuditLeak(
            area="Missed-call recovery",
            finding="Check whether missed callers receive an immediate text-back before they call a competitor.",
            recommended_module="Missed-Call Text-Back",
        ),
        AuditLeak(
            area="After-hours intake",
            finding="Emergency plumbing leads need a clear after-hours capture and escalation path.",
            recommended_module="AI Call Capture",
        ),
        AuditLeak(
            area="Quote follow-up",
            finding="Open estimates should be followed up automatically until won, lost, or escalated.",
            recommended_module="Quote Follow-Up",
        ),
    ]

    return AuditResponse(
        id=f"audit_{uuid4().hex[:12]}",
        status="queued",
        company_name=payload.company_name,
        summary=(
            "Audit request received. Owlbell will assess call capture, missed-call recovery, "
            "quote follow-up, reviews, and reactivation opportunities."
        ),
        likely_leaks=leaks,
        next_step="Send the written AI Ops Audit by email. No sales call required.",
    )
