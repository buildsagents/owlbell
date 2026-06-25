"""
Owlbell — Backend Package.

AI-powered 24/7 phone answering service for businesses.
Zero-budget, open-source stack: FreeSWITCH + Whisper + Ollama + Piper.

Subsystems:
- telephony: FreeSWITCH ESL integration
- ai: STT → LLM → TTS pipeline
- orchestrator: Session management, scaling, event bus
- business: Messages, appointments, routing, notifications
- integrations: Google Calendar, HubSpot, SendGrid, Twilio, Slack
- db: PostgreSQL models, repositories, Redis cache
- api: FastAPI REST endpoints
- operations: Tenant management, billing, audit, feature flags
"""

__version__ = "1.0.0"
__app_name__ = "Owlbell"
