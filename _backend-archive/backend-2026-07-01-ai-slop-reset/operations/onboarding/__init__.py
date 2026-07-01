"""Onboarding pipeline — automation, email sequences, admin routes."""

from __future__ import annotations

import backend.operations.onboarding.automation as automation
import backend.operations.onboarding.email_sequence as email_sequence

__all__ = ["automation", "email_sequence"]