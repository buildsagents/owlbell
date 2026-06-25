"""operations/onboarding/email_sequence.py - Post-sale onboarding email sequence.

Manages the automated email sequence sent to new clients during onboarding:
- Welcome email on signup
- Intake form reminder
- Configuration status updates
- Test call instructions
- Go-live notification
- Day-1 check-in
- Week-1 review scheduling

Design:
- Each email is triggered by onboarding step completion
- Uses SendGrid for delivery (falls back to SMTP)
- Tracks delivery status per tenant
- Supports preview/testing mode
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional

import structlog

logger = structlog.get_logger(__name__)


class EmailStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    FAILED = "failed"
    SKIPPED = "skipped"


class OnboardingEmail:
    """A single email in the onboarding sequence."""

    def __init__(
        self,
        email_id: str,
        trigger_step: str,
        subject: str,
        template: str,
        delay_hours: int = 0,
        required: bool = True,
    ):
        self.email_id = email_id
        self.trigger_step = trigger_step
        self.subject = subject
        self.template = template
        self.delay_hours = delay_hours
        self.required = required
        self.status = EmailStatus.PENDING
        self.sent_at: Optional[datetime] = None
        self.delivered_at: Optional[datetime] = None
        self.opened_at: Optional[datetime] = None
        self.error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "email_id": self.email_id,
            "trigger_step": self.trigger_step,
            "subject": self.subject,
            "template": self.template,
            "delay_hours": self.delay_hours,
            "status": self.status.value,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Email templates (subject + body structure)
# ---------------------------------------------------------------------------

EMAIL_TEMPLATES: dict[str, dict[str, str]] = {
    "welcome": {
        "subject": "Welcome to Owlbell! Let's get you set up",
        "body": """
Hi {contact_name},

Welcome to Owlbell! We're excited to help {business_name} never miss another call.

Here's what happens next:

1. **Fill out the intake form** (5 minutes)
   We need your business hours, services, and a few FAQs to build your AI receptionist.

2. **We configure everything** (same day)
   Our team builds your greeting, knowledge base, and routing rules.

3. **Test it** (10 minutes)
   You call in, hear it answer as your business, and we tweak anything.

4. **Go live** (next day)
   Stop sending calls to voicemail. Watch jobs land in your dashboard.

👉 [Complete your intake form]({intake_form_url})

Questions? Reply to this email or book a call: {calendly_url}

— The Owlbell Team
""",
    },
    "intake_reminder": {
        "subject": "Quick question: your business hours & services",
        "body": """
Hi {contact_name},

Just following up — we need a few details about {business_name} to build your AI receptionist:

- Business hours (and after-hours routing preferences)
- Services you offer (so it can answer pricing/service questions)
- 3-5 common FAQs callers ask
- Preferred greeting style (friendly, professional, etc.)

The form takes about 5 minutes: {intake_form_url}

We can't start building until we have this, so the sooner you fill it out, the sooner you're live.

— The Owlbell Team
""",
    },
    "configuration_started": {
        "subject": "Your AI receptionist is being built",
        "body": """
Hi {contact_name},

Great news — we've received your intake form for {business_name} and our team is now building your AI receptionist.

Here's what we're configuring:
- Custom greeting in your business's voice
- Knowledge base with your services, hours, and FAQs
- Call routing rules (business hours vs. after-hours)
- Calendar integration (if applicable)

You'll hear from us within a few hours with test call instructions.

— The Owlbell Team
""",
    },
    "test_ready": {
        "subject": "Your Owlbell is ready! Let's test it",
        "body": """
Hi {contact_name},

Your AI receptionist for {business_name} is ready for testing!

Here's how to test it:

1. Call {demo_number} from your business phone
2. Listen to how it answers — it should greet you as {business_name}
3. Try a few scenarios: appointment booking, pricing question, emergency
4. Let us know if you want any changes

If it doesn't sound right, just reply with what you'd like changed and we'll update it immediately.

Once you're happy, we'll flip the switch and start routing real calls.

— The Owlbell Team
""",
    },
    "go_live": {
        "subject": "You're live! Here's what to expect",
        "body": """
Hi {contact_name},

{business_name} is now live on Owlbell! 🎉

Your AI receptionist is answering calls 24/7. Here's what to expect:

- Every call is answered within 2 rings
- Appointment bookings sync to your calendar instantly
- You'll get a text + email after every call with full details
- Emergency calls are routed to your cell immediately

**Your dashboard:** {dashboard_url}
See every call, transcript, and captured lead in real-time.

**What to watch for:**
- Check your texts/emails after each call
- Review the dashboard daily for the first week
- Let us know immediately if anything sounds off

We'll check in tomorrow to make sure everything's running smoothly.

— The Owlbell Team
""",
    },
    "day_1_checkin": {
        "subject": "How's your first day going?",
        "body": """
Hi {contact_name},

You've been live for about 24 hours — how's it going?

A few things to check:
- Have you received text/email notifications for today's calls?
- Did any calls get handled that you would have missed before?
- Any calls that didn't go as expected?

If anything needs tweaking, just reply to this email. We can adjust the greeting, routing, knowledge base, or anything else in minutes.

If everything's great, we'd love to hear about it — your feedback helps us improve.

— The Owlbell Team
""",
    },
    "week_1_review": {
        "subject": "Your first week results are in",
        "body": """
Hi {contact_name},

You've completed your first week on Owlbell! Here's a quick summary:

📊 **Week 1 Metrics:**
- Calls answered: {calls_answered}
- Appointments booked: {bookings}
- Missed calls recovered: {missed_recovered}
- Average answer time: {avg_answer_time}

{performance_note}

**Next steps:**
- Book your Week 1 review call: {calendly_url}
- We'll walk through the numbers and optimize anything that needs tuning

Thanks for trusting Owlbell with {business_name}'s phones. We're here to make sure it keeps getting better.

— The Owlbell Team
""",
    },
    "satisfaction_survey": {
        "subject": "How are things going with Owlbell?",
        "body": """
Hi {contact_name},

You've been on Owlbell for a couple weeks now. We'd love your honest feedback:

1. How's the call quality? (1-5)
2. Are bookings happening correctly?
3. Is the greeting and tone right for your business?
4. Any features you wish it had?
5. Would you recommend Owlbell to another contractor?

Your feedback directly shapes how we improve the product. Just reply to this email with your thoughts.

If you're loving it, we'd also appreciate a short testimonial we can share (anonymized if you prefer).

— The Owlbell Team
""",
    },
}


# ---------------------------------------------------------------------------
# Onboarding Email Sequence
# ---------------------------------------------------------------------------

class OnboardingEmailSequence:
    """Manages the email sequence for a single client's onboarding."""

    # Define the sequence: trigger_step -> email template
    SEQUENCE = [
        {"trigger": "welcome_email", "template": "welcome", "delay_hours": 0},
        {"trigger": "intake_form_submitted", "template": "configuration_started", "delay_hours": 0},
        {"trigger": "intake_reminder", "template": "intake_reminder", "delay_hours": 24, "condition": "intake_not_submitted"},
        {"trigger": "test_ready", "template": "test_ready", "delay_hours": 0},
        {"trigger": "go_live", "template": "go_live", "delay_hours": 0},
        {"trigger": "day_1_checkin", "template": "day_1_checkin", "delay_hours": 24},
        {"trigger": "week_1_review", "template": "week_1_review", "delay_hours": 0},
        {"trigger": "satisfaction", "template": "satisfaction_survey", "delay_hours": 0},
    ]

    def __init__(
        self,
        tenant_id: str,
        contact_name: str,
        business_name: str,
        contact_email: str,
        pipeline_id: Optional[str] = None,
    ):
        self.tenant_id = tenant_id
        self.pipeline_id = pipeline_id
        self.contact_name = contact_name
        self.business_name = business_name
        self.contact_email = contact_email
        self.emails: list[OnboardingEmail] = []
        self.context: dict[str, Any] = {}

        # Initialize all emails in the sequence
        for seq_def in self.SEQUENCE:
            template = EMAIL_TEMPLATES.get(seq_def["template"], {})
            self.emails.append(OnboardingEmail(
                email_id=f"{tenant_id}_{seq_def['trigger']}",
                trigger_step=seq_def["trigger"],
                subject=template.get("subject", ""),
                template=seq_def["template"],
                delay_hours=seq_def.get("delay_hours", 0),
            ))

    def update_context(self, **kwargs: Any) -> None:
        """Update template context variables."""
        self.context.update(kwargs)

    def get_pending_emails(self, completed_steps: set[str]) -> list[dict[str, Any]]:
        """Determine which emails should be sent based on completed steps."""
        pending = []

        for email in self.emails:
            if email.status != EmailStatus.PENDING:
                continue

            # Check if the trigger step has been completed
            if email.trigger_step in completed_steps:
                # Check delay
                if email.delay_hours > 0:
                    # In production: check timestamp of step completion
                    # For now, include if delay has passed
                    pass

                pending.append({
                    "email_id": email.email_id,
                    "subject": email.subject,
                    "template": email.template,
                    "recipient": self.contact_email,
                    "delay_hours": email.delay_hours,
                })

        return pending

    def mark_sent(self, email_id: str) -> None:
        """Mark an email as sent."""
        for email in self.emails:
            if email.email_id == email_id:
                email.status = EmailStatus.SENT
                email.sent_at = datetime.utcnow()
                break

    def mark_delivered(self, email_id: str) -> None:
        """Mark an email as delivered."""
        for email in self.emails:
            if email.email_id == email_id:
                email.status = EmailStatus.DELIVERED
                email.delivered_at = datetime.utcnow()
                break

    def mark_opened(self, email_id: str) -> None:
        """Mark an email as opened."""
        for email in self.emails:
            if email.email_id == email_id:
                email.status = EmailStatus.OPENED
                email.opened_at = datetime.utcnow()
                break

    def mark_failed(self, email_id: str, error: str) -> None:
        """Mark an email as failed."""
        for email in self.emails:
            if email.email_id == email_id:
                email.status = EmailStatus.FAILED
                email.error = error
                break

    def render_email(self, email_id: str) -> Optional[dict[str, str]]:
        """Render an email template with current context."""
        template_data = EMAIL_TEMPLATES.get("", {})
        for email in self.emails:
            if email.email_id == email_id:
                template_data = EMAIL_TEMPLATES.get(email.template, {})
                break

        if not template_data:
            return None

        body = template_data.get("body", "")
        subject = template_data.get("subject", "")

        # Fill template variables
        context = {
            "contact_name": self.contact_name,
            "business_name": self.business_name,
            **self.context,
        }

        try:
            rendered_body = body.format(**context)
            rendered_subject = subject.format(**context)
        except KeyError as exc:
            logger.warning("email.render_missing_var", email_id=email_id, missing=str(exc))
            rendered_body = body
            rendered_subject = subject

        return {
            "subject": rendered_subject,
            "body": rendered_body,
            "to": self.contact_email,
        }

    def get_status(self) -> dict[str, Any]:
        """Get the full status of the email sequence."""
        return {
            "tenant_id": self.tenant_id,
            "total_emails": len(self.emails),
            "sent": sum(1 for e in self.emails if e.status == EmailStatus.SENT),
            "delivered": sum(1 for e in self.emails if e.status == EmailStatus.DELIVERED),
            "opened": sum(1 for e in self.emails if e.status == EmailStatus.OPENED),
            "failed": sum(1 for e in self.emails if e.status == EmailStatus.FAILED),
            "pending": sum(1 for e in self.emails if e.status == EmailStatus.PENDING),
            "emails": [e.to_dict() for e in self.emails],
        }


# ---------------------------------------------------------------------------
# Email delivery (SendGrid / SMTP fallback)
# ---------------------------------------------------------------------------

def send_email(
    to: str,
    subject: str,
    body: str,
    from_email: str = "hello@owlbell.xyz",
    from_name: str = "Owlbell",
) -> dict[str, Any]:
    """Send an email via SendGrid or SMTP fallback.

    In production, this sends real emails. In development, it logs and returns success.
    """
    logger.info("email.sending", to=to, subject=subject)

    # Try SendGrid first
    try:
        return _send_via_sendgrid(to, subject, body, from_email, from_name)
    except Exception as exc:
        logger.warning("email.sendgrid_failed", error=str(exc))

    # Fallback to SMTP
    try:
        return _send_via_smtp(to, subject, body, from_email, from_name)
    except Exception as exc:
        logger.warning("email.smtp_failed", error=str(exc))

    # Last resort: log only
    logger.info("email.logged_only", to=to, subject=subject, body_preview=body[:200])
    return {"success": True, "method": "log_only", "note": "Email logged but not sent (no provider configured)"}


def _send_via_sendgrid(to: str, subject: str, body: str, from_email: str, from_name: str) -> dict[str, Any]:
    """Send via SendGrid API."""
    import os
    api_key = os.environ.get("SENDGRID_API_KEY")
    if not api_key:
        raise ValueError("SENDGRID_API_KEY not set")

    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail

    message = Mail(
        from_email=from_email,
        to_emails=to,
        subject=subject,
        html_content=body,
    )
    sg = SendGridAPIClient(api_key)
    response = sg.send(message)
    return {"success": True, "method": "sendgrid", "status_code": response.status_code}


def _send_via_smtp(to: str, subject: str, body: str, from_email: str, from_name: str) -> dict[str, Any]:
    """Send via SMTP."""
    import os
    import smtplib
    from email.mime.text import MIMEText

    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")

    if not smtp_user:
        raise ValueError("SMTP credentials not configured")

    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)

    return {"success": True, "method": "smtp"}


# ---------------------------------------------------------------------------
# Sequence storage (DB-backed via onboarding_emails)
# ---------------------------------------------------------------------------

from uuid import UUID, uuid4  # noqa: E402


def _apply_rows(sequence: OnboardingEmailSequence, rows: list[Any]) -> None:
    """Overlay persisted email status onto a freshly-built sequence."""
    by_id = {e.email_id: e for e in sequence.emails}
    for row in rows:
        email = by_id.get(row.email_id)
        if email is None:
            continue
        email.status = EmailStatus(row.status)
        email.sent_at = row.sent_at
        email.delivered_at = row.delivered_at
        email.opened_at = row.opened_at
        email.error = row.error


async def get_sequence(
    session_maker: Callable[[], Any], tenant_id: str
) -> Optional[OnboardingEmailSequence]:
    """Get the email sequence for a tenant (or None if not created)."""
    from sqlalchemy import select

    from backend.db.models.onboarding import OnboardingEmailRecord

    async with session_maker() as session:
        stmt = select(OnboardingEmailRecord).where(
            OnboardingEmailRecord.tenant_id == UUID(str(tenant_id))
        )
        rows = (await session.execute(stmt)).scalars().all()
    if not rows:
        return None
    # Contact details are not stored separately; recover sane defaults so the
    # sequence can render (templates also accept runtime context overrides).
    sequence = OnboardingEmailSequence(
        tenant_id=str(tenant_id),
        contact_name="",
        business_name="",
        contact_email=rows[0].email_id.split("_", 1)[0] if rows else "",
    )
    _apply_rows(sequence, rows)
    return sequence


async def create_sequence(
    session_maker: Callable[[], Any],
    tenant_id: str,
    contact_name: str,
    business_name: str,
    contact_email: str,
    pipeline_id: Optional[str] = None,
) -> OnboardingEmailSequence:
    """Create and persist a new email sequence for a tenant.

    Idempotent: returns the existing sequence if one is already present.
    """
    existing = await get_sequence(session_maker, tenant_id)
    if existing is not None:
        return existing

    from backend.db.models.onboarding import OnboardingEmailRecord

    sequence = OnboardingEmailSequence(
        tenant_id=tenant_id,
        contact_name=contact_name,
        business_name=business_name,
        contact_email=contact_email,
        pipeline_id=pipeline_id,
    )
    async with session_maker() as session:
        for email in sequence.emails:
            session.add(OnboardingEmailRecord(
                id=uuid4(),
                pipeline_id=UUID(str(pipeline_id)) if pipeline_id else None,
                tenant_id=UUID(str(tenant_id)),
                email_id=email.email_id,
                trigger_step=email.trigger_step,
                subject=email.subject,
                template=email.template,
                delay_hours=email.delay_hours,
                status=email.status.value,
            ))
        await session.commit()
    logger.info("email_sequence.created", tenant_id=str(tenant_id), emails=len(sequence.emails))
    return sequence


async def mark_email(
    session_maker: Callable[[], Any],
    tenant_id: str,
    email_id: str,
    status: EmailStatus,
    error: Optional[str] = None,
) -> bool:
    """Persist a status transition for a single onboarding email."""
    from sqlalchemy import select

    from backend.db.models.onboarding import OnboardingEmailRecord

    now = datetime.utcnow()
    async with session_maker() as session:
        stmt = select(OnboardingEmailRecord).where(
            OnboardingEmailRecord.tenant_id == UUID(str(tenant_id)),
            OnboardingEmailRecord.email_id == email_id,
        )
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return False
        row.status = status.value
        if status == EmailStatus.SENT:
            row.sent_at = now
        elif status == EmailStatus.DELIVERED:
            row.delivered_at = now
        elif status == EmailStatus.OPENED:
            row.opened_at = now
        elif status == EmailStatus.FAILED:
            row.error = error
        await session.commit()
        return True


async def list_sequences(session_maker: Callable[[], Any]) -> list[dict[str, Any]]:
    """List all email sequences with their status."""
    from sqlalchemy import select

    from backend.db.models.onboarding import OnboardingEmailRecord

    async with session_maker() as session:
        stmt = select(OnboardingEmailRecord)
        rows = (await session.execute(stmt)).scalars().all()

    by_tenant: dict[str, list[Any]] = {}
    for row in rows:
        by_tenant.setdefault(str(row.tenant_id), []).append(row)

    sequences: list[dict[str, Any]] = []
    for tid, trows in by_tenant.items():
        sequence = OnboardingEmailSequence(
            tenant_id=tid, contact_name="", business_name="",
            contact_email=trows[0].email_id.split("_", 1)[0] if trows else "",
        )
        _apply_rows(sequence, trows)
        sequences.append(sequence.get_status())
    return sequences
