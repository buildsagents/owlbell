import { NextResponse } from "next/server";
import { DEPRECATED_WEBHOOK_MESSAGE, FASTAPI_V1 } from "@/lib/consolidation";

/**
 * Proxies onboarding intake to FastAPI (single source of truth).
 * Kept so existing /api/onboarding/intake callers keep working during migration.
 */
export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ ok: false, error: "invalid_json" }, { status: 400 });
  }

  try {
    const res = await fetch(`${FASTAPI_V1}/onboarding/intake`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    const json = await res.json();
    if (!res.ok) {
      return NextResponse.json(
        { ok: false, error: json.detail || "upstream_error" },
        { status: res.status }
      );
    }
    return NextResponse.json(json);
  } catch (err) {
    console.error("[onboarding/intake] FastAPI proxy failed:", err);
    return NextResponse.json({ ok: false, error: "upstream_unavailable" }, { status: 502 });
  }
}

export async function GET() {
  return NextResponse.json(
    {
      deprecated: true,
      message: DEPRECATED_WEBHOOK_MESSAGE,
      use: `${FASTAPI_V1}/onboarding/intake`,
    },
    { status: 410 }
  );
}