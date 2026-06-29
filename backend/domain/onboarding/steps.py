"""Canonical onboarding pipeline step definitions.

Re-exports from operations.onboarding.automation so domain and ops share one source.
"""

from backend.operations.onboarding.automation import DEFAULT_PIPELINE_STEPS, ONBOARDING_EMAILS

# Plan-aligned aliases (map to persisted step_id values)
STEP_PAYMENT_RECEIVED = "welcome_email"
STEP_INTAKE_SUBMITTED = "intake_form"
STEP_RETELL_PROVISIONED = "ai_configuration"
STEP_PHONE_PROVISIONED = "phone_setup"
STEP_TEST_CALLS = "test_calls"
STEP_GO_LIVE = "go_live"

__all__ = [
    "DEFAULT_PIPELINE_STEPS",
    "ONBOARDING_EMAILS",
    "STEP_PAYMENT_RECEIVED",
    "STEP_INTAKE_SUBMITTED",
    "STEP_RETELL_PROVISIONED",
    "STEP_PHONE_PROVISIONED",
    "STEP_TEST_CALLS",
    "STEP_GO_LIVE",
]