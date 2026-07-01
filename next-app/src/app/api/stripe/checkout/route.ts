import { NextResponse } from "next/server";
import { DEPRECATED_WEBHOOK_MESSAGE, FASTAPI_V1 } from "@/lib/consolidation";

/** Deprecated - use FastAPI public-checkout from the marketing site. */
export async function POST() {
  return NextResponse.json(
    {
      error: "gone",
      message: DEPRECATED_WEBHOOK_MESSAGE,
      use: `${FASTAPI_V1}/billing/public-checkout`,
    },
    { status: 410 }
  );
}