"""Frozen legacy subsystems (FreeSWITCH ESL, call orchestrator).

Not loaded in production unless ``FEATURE_ENABLE_LEGACY_FREESWITCH=true``.
Production call ingress is Retell webhooks → FastAPI.
"""