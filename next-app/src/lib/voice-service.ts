/**
 * Voice platform service wrapper — supports Retell AI and Vapi.
 *
 * Set VOICE_PROVIDER=retell or vapi in .env.local.
 * Set RETELL_API_KEY or VAPI_API_KEY accordingly.
 */

import { Agent, Call, CallTranscriptTurn, CallActionItems } from '@/types';

const PROVIDER = (process.env.VOICE_PROVIDER ?? 'retell') as 'retell' | 'vapi';
const RETELL_API_KEY = process.env.RETELL_API_KEY;
const VAPI_API_KEY   = process.env.VAPI_API_KEY;

// ---------------------------------------------------------------------------
// Provision a new AI agent for an org
// ---------------------------------------------------------------------------
export async function createVoiceAgent(params: {
  greeting: string;
  systemPrompt: string;
  voiceId?: string;
  phoneNumber?: string;
}): Promise<string | null> {
  if (PROVIDER === 'retell') {
    const res = await fetch('https://api.retellai.com/create-agent', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${RETELL_API_KEY}`,
      },
      body: JSON.stringify({
        agent_name: `Owlbell Agent`,
        response_engine: { type: 'retell-llm' },
        voice_id: params.voiceId ?? '11labs-Adrian',
        begin_message: params.greeting,
        general_prompt: params.systemPrompt,
      }),
    });
    if (!res.ok) {
      console.error('[voice] Retell agent creation failed:', await res.text());
      return null;
    }
    const data = await res.json();
    return data.agent_id as string;
  }

  if (PROVIDER === 'vapi') {
    const res = await fetch('https://api.vapi.ai/assistant', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${VAPI_API_KEY}`,
      },
      body: JSON.stringify({
        name: 'Owlbell Agent',
        firstMessage: params.greeting,
        model: {
          provider: 'openai',
          model: 'gpt-4o-mini',
          systemPrompt: params.systemPrompt,
        },
        voice: {
          provider: 'cartesia',
          voiceId: params.voiceId ?? '79a125e8-cd45-4c13-8a67-188112f4dd22',
        },
      }),
    });
    if (!res.ok) {
      console.error('[voice] Vapi agent creation failed:', await res.text());
      return null;
    }
    const data = await res.json();
    return data.id as string;
  }

  return null;
}

// ---------------------------------------------------------------------------
// Update an existing agent's prompt/greeting
// ---------------------------------------------------------------------------
export async function updateVoiceAgent(
  providerAgentId: string,
  params: { greeting?: string; systemPrompt?: string; voiceId?: string }
): Promise<boolean> {
  if (PROVIDER === 'retell') {
    const res = await fetch(`https://api.retellai.com/update-agent/${providerAgentId}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${RETELL_API_KEY}`,
      },
      body: JSON.stringify({
        ...(params.greeting && { begin_message: params.greeting }),
        ...(params.systemPrompt && { general_prompt: params.systemPrompt }),
        ...(params.voiceId && { voice_id: params.voiceId }),
      }),
    });
    return res.ok;
  }

  if (PROVIDER === 'vapi') {
    const res = await fetch(`https://api.vapi.ai/assistant/${providerAgentId}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${VAPI_API_KEY}`,
      },
      body: JSON.stringify({
        ...(params.greeting && { firstMessage: params.greeting }),
        ...(params.systemPrompt && {
          model: { systemPrompt: params.systemPrompt },
        }),
      }),
    });
    return res.ok;
  }

  return false;
}

// ---------------------------------------------------------------------------
// Parse a Retell or Vapi post-call webhook into our unified Call shape
// ---------------------------------------------------------------------------
export function parseCallWebhook(payload: any): Partial<Call> & {
  provider_call_id: string;
} {
  if (PROVIDER === 'retell') {
    const transcript: CallTranscriptTurn[] = (payload.transcript ?? []).map(
      (t: any) => ({ role: t.role === 'agent' ? 'agent' : 'user', content: t.content })
    );

    const actions: CallActionItems = extractActionItems(
      payload.call_analysis?.custom_analysis_data ?? {},
      payload.transcript_object ?? []
    );

    return {
      provider_call_id: payload.call_id,
      caller_number: payload.from_number ?? '',
      duration_seconds: Math.round((payload.end_timestamp - payload.start_timestamp) / 1000),
      status: payload.disconnection_reason === 'hangup' ? 'completed' : 'failed',
      recording_url: payload.recording_url ?? null,
      transcript,
      summary: payload.call_analysis?.call_summary ?? null,
      action_items: actions,
    };
  }

  if (PROVIDER === 'vapi') {
    const transcript: CallTranscriptTurn[] = (payload.artifact?.transcript ?? []).map(
      (t: any) => ({ role: t.role === 'assistant' ? 'agent' : 'user', content: t.transcript })
    );

    const actions: CallActionItems = extractActionItems(
      payload.analysis ?? {},
      transcript
    );

    return {
      provider_call_id: payload.call?.id ?? '',
      caller_number: payload.call?.customer?.number ?? '',
      duration_seconds: Math.round((payload.call?.endedAt - payload.call?.startedAt) / 1000) || 0,
      status: payload.call?.endedReason === 'hangup' ? 'completed' : 'failed',
      recording_url: payload.artifact?.recordingUrl ?? null,
      transcript,
      summary: payload.analysis?.summary ?? null,
      action_items: actions,
    };
  }

  return { provider_call_id: '' };
}

// ---------------------------------------------------------------------------
// LLM-free heuristic extraction of action items from transcript
// For a production system, replace with a structured LLM extraction call.
// ---------------------------------------------------------------------------
function extractActionItems(
  analysis: Record<string, any>,
  transcript: CallTranscriptTurn[]
): CallActionItems {
  const fullText = transcript.map((t) => t.content).join(' ').toLowerCase();

  const isEmergency =
    fullText.includes('emergency') ||
    fullText.includes('burst') ||
    fullText.includes('flood') ||
    fullText.includes('no power') ||
    fullText.includes('outage') ||
    analysis?.is_emergency === true;

  const appointmentBooked =
    fullText.includes('booked') ||
    fullText.includes('scheduled') ||
    fullText.includes('appointment') ||
    analysis?.appointment_booked === true;

  // Extract caller name from analysis if provided by the LLM
  const callerName = analysis?.caller_name ?? undefined;
  const callerPhone = analysis?.caller_phone ?? undefined;
  const callerAddress = analysis?.caller_address ?? undefined;
  const appointmentDatetime = analysis?.appointment_datetime ?? undefined;

  return {
    is_emergency: Boolean(isEmergency),
    appointment_booked: Boolean(appointmentBooked),
    caller_name: callerName,
    caller_phone: callerPhone,
    caller_address: callerAddress,
    appointment_datetime: appointmentDatetime,
  };
}
