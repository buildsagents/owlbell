/** Canonical URLs after Phase 1 architecture consolidation. */

export const FASTAPI_BASE = (
  process.env.NEXT_PUBLIC_API_URL || "https://owlbell-api-production.up.railway.app"
).replace(/\/+$/, "");

export const FASTAPI_V1 = `${FASTAPI_BASE}/api/v1`;

export const DASHBOARD_APP_URL = (
  process.env.NEXT_PUBLIC_DASHBOARD_URL || "https://app.owlbell.xyz"
).replace(/\/+$/, "");

export const DEPRECATED_WEBHOOK_MESSAGE =
  "This endpoint is deprecated. Configure webhooks on the FastAPI API only.";