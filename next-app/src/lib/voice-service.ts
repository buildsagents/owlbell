import { Call, CallActionItems, CallTranscriptTurn } from "@/types";

const RETELL_API_KEY = process.env.RETELL_API_KEY || process.env.INTEGRATION_RETELL_API_KEY;
const RETELL_DEFAULT_VOICE_ID = "retell-Willa";

type RetellTranscriptTurn = {
  role?: string;
  content?: string;
  transcript?: string;
  text?: string;
};

type RetellCallPayload = Record<string, any>;

async function retellFetch(path: string, body: Record<string, unknown>) {
  if (!RETELL_API_KEY) return null;

  const res = await fetch(`https://api.retellai.com${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${RETELL_API_KEY}`,
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    console.error("[voice] Retell request failed:", path, res.status, await res.text());
    return null;
  }

  return res.json();
}

export async function createVoiceAgent(params: {
  greeting: string;
  systemPrompt: string;
  voiceId?: string;
  phoneNumber?: string;
}): Promise<string | null> {
  const llm = await retellFetch("/create-retell-llm", {
    general_prompt: params.systemPrompt,
    begin_message: params.greeting,
    model: "gpt-4.1-mini",
    model_temperature: 0.35,
  }) as { llm_id?: string } | null;

  if (!llm?.llm_id) return null;

  const agent = await retellFetch("/create-agent", {
    agent_name: "Owlbell Receptionist",
    response_engine: { type: "retell-llm", llm_id: llm.llm_id },
    voice_id: params.voiceId || RETELL_DEFAULT_VOICE_ID,
    language: "en-US",
    enable_backchannel: true,
    interruption_sensitivity: 0.75,
    responsiveness: 0.85,
    metadata: params.phoneNumber ? { phoneNumber: params.phoneNumber } : undefined,
  }) as { agent_id?: string } | null;

  return agent?.agent_id ?? null;
}

export async function updateVoiceAgent(
  providerAgentId: string,
  params: { greeting?: string; systemPrompt?: string; voiceId?: string }
): Promise<boolean> {
  const responseEngine = params.systemPrompt
    ? {
      type: "retell-llm",
      general_prompt: params.systemPrompt,
      begin_message: params.greeting,
    }
    : undefined;

  const result = await retellFetch(`/update-agent/${providerAgentId}`, {
    ...(responseEngine ? { response_engine: responseEngine } : {}),
    ...(params.voiceId ? { voice_id: params.voiceId } : {}),
  });

  return Boolean(result);
}

export function parseCallWebhook(payload: RetellCallPayload): Partial<Call> & {
  provider_call_id: string;
} {
  const call = payload.call ?? payload;
  const transcript = parseTranscript(payload.transcript ?? payload.artifact?.transcript ?? []);
  const durationMs = call.duration_ms ?? payload.duration_ms;
  const startedAt = call.start_timestamp ?? call.startedAt;
  const endedAt = call.end_timestamp ?? call.endedAt;
  const durationSeconds = typeof durationMs === "number"
    ? Math.round(durationMs / 1000)
    : Math.round(((endedAt ?? 0) - (startedAt ?? 0)) / 1000) || 0;

  const actions = extractActionItems(payload.summary ?? payload.analysis ?? {}, transcript);
  const result = call.call_result ?? payload.call_result ?? call.endedReason;

  return {
    provider_call_id: call.call_id ?? payload.call_id ?? call.id ?? "",
    caller_number: call.from_number ?? call.caller_number ?? call.customer?.number ?? payload.caller_number ?? "",
    duration_seconds: durationSeconds,
    status: result === "completed" || result === "hangup" ? "completed" : "failed",
    recording_url: call.recording_url ?? payload.recording_url ?? payload.artifact?.recordingUrl ?? null,
    transcript,
    summary: typeof payload.summary === "string" ? payload.summary : payload.summary?.summary ?? payload.analysis?.summary ?? null,
    action_items: actions,
  };
}

function parseTranscript(transcript: unknown): CallTranscriptTurn[] {
  if (typeof transcript === "string") {
    return transcript
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const isAgent = /^(agent|assistant):/i.test(line);
        return {
          role: isAgent ? "agent" : "user",
          content: line.replace(/^(agent|assistant|user|caller):\s*/i, ""),
        };
      });
  }

  if (!Array.isArray(transcript)) return [];

  return transcript.map((turn: RetellTranscriptTurn) => {
    const role = String(turn.role ?? "").toLowerCase();
    const normalizedRole: CallTranscriptTurn["role"] =
      role === "agent" || role === "assistant" ? "agent" : "user";
    return {
      role: normalizedRole,
      content: turn.content ?? turn.transcript ?? turn.text ?? "",
    };
  }).filter((turn) => turn.content);
}

function extractActionItems(
  analysis: Record<string, any>,
  transcript: CallTranscriptTurn[]
): CallActionItems {
  const fullText = transcript.map((t) => t.content).join(" ").toLowerCase();

  const isEmergency =
    fullText.includes("emergency") ||
    fullText.includes("burst") ||
    fullText.includes("flood") ||
    fullText.includes("no power") ||
    fullText.includes("outage") ||
    analysis?.is_emergency === true ||
    analysis?.urgency === "emergency";

  const appointmentBooked =
    fullText.includes("booked") ||
    fullText.includes("scheduled") ||
    fullText.includes("appointment") ||
    analysis?.appointment_booked === true;

  return {
    is_emergency: Boolean(isEmergency),
    appointment_booked: Boolean(appointmentBooked),
    caller_name: analysis?.caller_name ?? undefined,
    caller_phone: analysis?.caller_phone ?? undefined,
    caller_address: analysis?.caller_address ?? undefined,
    appointment_datetime: analysis?.appointment_datetime ?? undefined,
  };
}
