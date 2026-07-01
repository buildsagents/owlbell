import { NextResponse } from "next/server";

export async function POST() {
  const apiKey = process.env.RETELL_API_KEY || process.env.INTEGRATION_RETELL_API_KEY;
  const agentId =
    process.env.RETELL_DEMO_AGENT_ID ||
    process.env.NEXT_PUBLIC_RETELL_DEMO_AGENT_ID ||
    "agent_233aac32d03d073ad7774a5ca2";

  if (!apiKey) {
    return NextResponse.json({ error: "retell_not_configured" }, { status: 503 });
  }

  const retellRes = await fetch("https://api.retellai.com/v2/create-web-call", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      agent_id: agentId,
      retell_llm_dynamic_variables: {
        business_name: "Northstar Plumbing",
        business_hours: "Monday to Friday 8 AM to 6 PM, emergency cover after hours",
        services: "Emergency plumbing, burst pipes, leaks, blocked drains, boiler callouts",
        pricing_info: "Emergency callouts are triaged first. Final pricing depends on the job.",
        booking_link: "https://owlbell.xyz/onboarding",
        business_address: "Bristol, UK",
        business_phone: "+441174960000",
        transfer_number: "+441174960000",
        faq_emergency_contacts: "For active flooding, collect address and callback number, give safety guidance, and escalate to the on-call plumber.",
      },
      metadata: {
        source: "owlbell_public_demo",
      },
    }),
  });

  if (!retellRes.ok) {
    const detail = await retellRes.text();
    console.error("[demo] Retell web call failed:", retellRes.status, detail);
    return NextResponse.json({ error: "retell_web_call_failed" }, { status: 502 });
  }

  const data = await retellRes.json();
  return NextResponse.json({
    provider: "retell",
    access_token: data.access_token,
    call_id: data.call_id,
    agent_id: data.agent_id,
  });
}
