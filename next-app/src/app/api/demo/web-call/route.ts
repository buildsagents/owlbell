import { NextResponse } from "next/server";

/**
 * Mints a Retell web-call access token for the homepage "Talk to OwlBell" demo.
 *
 * Server-side only — the RETELL_API_KEY never reaches the browser. The browser
 * receives just a short-lived access_token, which RetellWebClient uses to start
 * the WebRTC call. Mirrors the proven backend /test-token flow.
 */
export async function POST(request: Request) {
  const apiKey = process.env.RETELL_API_KEY;
  const agentId = process.env.RETELL_DEMO_AGENT_ID ?? "agent_5a047acc926ea98243a7072218";

  if (!apiKey) {
    // Not an error the user caused — the client gracefully falls back to the film.
    return NextResponse.json({ error: "voice_not_configured" }, { status: 503 });
  }

  let dynamicVariables: Record<string, string> = {};
  try {
    const body = await request.json();
    dynamicVariables = body?.dynamic_variables ?? {};
  } catch {
    /* empty body is fine */
  }

  try {
    const res = await fetch("https://api.retellai.com/v2/create-web-call", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        agent_id: agentId,
        retell_llm_dynamic_variables: dynamicVariables,
      }),
    });

    if (!res.ok) {
      const detail = await res.text();
      console.error("[demo/web-call] Retell error:", res.status, detail);
      return NextResponse.json({ error: "retell_failed" }, { status: 502 });
    }

    const data = await res.json();
    return NextResponse.json({
      call_id: data.call_id,
      access_token: data.access_token,
    });
  } catch (err) {
    console.error("[demo/web-call] exception:", err);
    return NextResponse.json({ error: "exception" }, { status: 500 });
  }
}
