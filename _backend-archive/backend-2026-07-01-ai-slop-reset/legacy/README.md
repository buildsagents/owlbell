# Legacy subsystems (frozen)

These packages are **not used in production** for the consolidated Owlbell stack.

| Package | Purpose | Replacement |
|---------|---------|-------------|
| `legacy/orchestrator/` | FreeSWITCH call orchestration, Celery tasks, WebSocket gateway | Retell webhooks + `domain/` services |
| `legacy/telephony/` | FreeSWITCH ESL integration | Retell AI + Twilio SIP |

Enable locally with `FEATURE_ENABLE_LEGACY_FREESWITCH=true`.

Shim packages at `backend/orchestrator/` and `backend/telephony/` re-export from here for backward-compatible imports.