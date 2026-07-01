import { NextResponse } from "next/server";

type OnboardingPayload = {
  step1_businessInfo?: {
    companyName?: string;
    ownerName?: string;
    email?: string;
    mobile?: string;
    businessAddress?: string;
    website?: string;
  };
  step2_businessDetails?: {
    openingHours?: string;
    emergencyAvailable?: boolean;
    serviceAreas?: string;
    servicesOffered?: string[];
    typicalPricing?: string;
    preferredGreeting?: string;
  };
  step3_callHandling?: {
    bookingRules?: string;
    emergencyRouting?: string;
    outOfHoursBehavior?: string;
    transferNumbers?: string[];
    voicemailPreferences?: string;
  };
  step5_knowledgeBase?: {
    faqs?: string;
    priceList?: string;
    serviceInfo?: string;
    policies?: string;
    websiteUrl?: string;
  };
  step6_phoneNumbers?: {
    type?: string;
    desiredNumber?: string;
    existingNumber?: string;
  };
  step7_aiVoice?: {
    voiceId?: string;
    voiceName?: string;
    speakingStyle?: string;
  };
};

const RETELL_DEFAULT_VOICE_ID = "retell-Willa";

function text(value: unknown, fallback = "") {
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

function joinList(value: unknown, fallback = "") {
  return Array.isArray(value) && value.length > 0
    ? value.map((item) => String(item).trim()).filter(Boolean).join(", ")
    : fallback;
}

function buildSystemPrompt(payload: OnboardingPayload) {
  const business = payload.step1_businessInfo ?? {};
  const details = payload.step2_businessDetails ?? {};
  const handling = payload.step3_callHandling ?? {};
  const kb = payload.step5_knowledgeBase ?? {};

  const companyName = text(business.companyName, "the plumbing company");
  const services = joinList(details.servicesOffered, "emergency plumbing, leaks, blocked drains, boiler callouts");
  const serviceArea = text(details.serviceAreas, "the local service area");
  const openingHours = text(details.openingHours, "business hours");
  const pricing = text(details.typicalPricing, "Pricing depends on the job. Do not quote exact prices.");
  const routing = text(handling.emergencyRouting, "escalate_emergency");
  const outOfHours = text(handling.outOfHoursBehavior, "take a message and alert the owner");
  const bookingRules = text(handling.bookingRules, "Book only when the caller is inside the service area and the request matches the shop rules.");
  const transferNumbers = joinList(handling.transferNumbers, text(business.mobile, "the owner number"));

  return `You are Morgan, a calm receptionist for ${companyName}.

You are not a generic chatbot. Speak like a trained front-desk receptionist: short answers, one question at a time, no hype, no repeated filler.

Business details:
- Service area: ${serviceArea}
- Hours: ${openingHours}
- Services: ${services}
- Pricing guardrail: ${pricing}
- Booking rules: ${bookingRules}
- Emergency routing: ${routing}
- Out-of-hours handling: ${outOfHours}
- Transfer numbers: ${transferNumbers}

Call handling rules:
- Start by asking whether this is an emergency or a routine booking.
- For active leaks, flooding, sewage backup, gas smell, no heating for vulnerable occupants, or unsafe electrical-water situations, classify the call as urgent.
- For active water leaks, ask whether the stopcock is off if it is safe for the caller to check.
- Always collect caller name, callback number, full address, issue, urgency, and access notes.
- Never promise exact pricing or arrival times outside the business rules.
- If the caller is upset, slow down and acknowledge the issue before asking the next question.
- End by confirming what happens next and whether the caller will receive a text or callback.

Knowledge base:
FAQs: ${text(kb.faqs, "No extra FAQs supplied.")}
Price list: ${text(kb.priceList, "No detailed price list supplied.")}
Service info: ${text(kb.serviceInfo, "No extra service notes supplied.")}
Policies: ${text(kb.policies, "No extra policies supplied.")}`;
}

async function createRetellDraft(payload: OnboardingPayload, apiKey: string) {
  const business = payload.step1_businessInfo ?? {};
  const details = payload.step2_businessDetails ?? {};
  const voice = payload.step7_aiVoice ?? {};
  const companyName = text(business.companyName, "Owlbell Client");
  const voiceId = text(voice.voiceId, RETELL_DEFAULT_VOICE_ID);
  const beginMessage = text(
    details.preferredGreeting,
    `Thanks for calling ${companyName}, this is Morgan. Are you calling about an emergency, or would you like to book a visit?`,
  ).replace("{company}", companyName).replace("{name}", text(voice.voiceName, "Morgan"));

  const llmRes = await fetch("https://api.retellai.com/create-retell-llm", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      general_prompt: buildSystemPrompt(payload),
      begin_message: beginMessage,
      model: "gpt-4.1-mini",
      model_temperature: 0.35,
    }),
  });

  if (!llmRes.ok) {
    const detail = await llmRes.text();
    throw new Error(`Retell LLM creation failed: ${llmRes.status} ${detail}`);
  }

  const llm = await llmRes.json() as { llm_id?: string };
  if (!llm.llm_id) throw new Error("Retell LLM response missing llm_id");

  const agentRes = await fetch("https://api.retellai.com/create-agent", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      agent_name: `${companyName} Receptionist`,
      response_engine: { type: "retell-llm", llm_id: llm.llm_id },
      voice_id: voiceId,
      language: "en-US",
      enable_backchannel: true,
      interruption_sensitivity: 0.75,
      responsiveness: 0.85,
    }),
  });

  if (!agentRes.ok) {
    const detail = await agentRes.text();
    throw new Error(`Retell agent creation failed: ${agentRes.status} ${detail}`);
  }

  const agent = await agentRes.json() as { agent_id?: string };
  if (!agent.agent_id) throw new Error("Retell agent response missing agent_id");

  return {
    llmId: llm.llm_id,
    agentId: agent.agent_id,
  };
}

export async function POST(request: Request) {
  try {
    const body = await request.json() as OnboardingPayload;
    const business = body.step1_businessInfo ?? {};

    if (!business.companyName || !business.email) {
      return NextResponse.json({ error: "Missing required business info" }, { status: 400 });
    }

    const apiKey = process.env.RETELL_API_KEY || process.env.INTEGRATION_RETELL_API_KEY;
    if (!apiKey) {
      return NextResponse.json({
        success: true,
        provider: "retell",
        status: "queued",
        message: "Setup package received. Retell credentials are not configured in this environment, so the build is queued for managed setup.",
      });
    }

    const draft = await createRetellDraft(body, apiKey);

    return NextResponse.json({
      success: true,
      provider: "retell",
      status: "draft_created",
      agentId: draft.agentId,
      llmId: draft.llmId,
      message: "Retell receptionist draft created. Next step: test calls, script tuning, then forwarding.",
    });
  } catch (err) {
    console.error("[provision] Retell setup failed:", err);
    return NextResponse.json({ error: "Retell setup failed" }, { status: 502 });
  }
}
