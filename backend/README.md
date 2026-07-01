# Owlbell Backend

Clean FastAPI baseline for the Owlbell AI operations agency.

## Current Scope

- Health/readiness endpoints for Railway.
- AI Ops audit request endpoint.
- Product module catalog.
- Retell and Stripe webhook placeholders.

## Principles

- Keep routes explicit.
- Keep integrations behind service/adaptor modules.
- Do not rebuild the old generated backend unless a real client workflow requires it.
- Add one workflow at a time: audit, call capture, missed-call text-back, reports, quote follow-up, reviews, reactivation.

## Local Run

```bash
pip install -r backend/requirements-cloud.txt
uvicorn backend.app_factory:create_app --factory --reload
```
