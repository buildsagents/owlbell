import { NextResponse } from 'next/server';
import { createClient } from '@/lib/supabase/server';
import { parseCallWebhook } from '@/lib/voice-service';

export async function POST(request: Request) {
  try {
    const payload = await request.json();

    // Parse provider-specific webhook into unified shape
    const callData = parseCallWebhook(payload);

    if (!callData.provider_call_id) {
      return NextResponse.json({ error: 'Missing call ID in webhook' }, { status: 400 });
    }

    // Resolve org_id from the agent's provider_agent_id
    const supabase = await createClient();
    const agentId = payload.agent_id ?? payload.call?.assistantId ?? null;

    let orgId: string | null = null;
    if (agentId) {
      const { data: agent } = await supabase
        .from('agents')
        .select('org_id, id')
        .eq('provider_agent_id', agentId)
        .single();

      if (agent) {
        orgId = agent.org_id;
        (callData as any).agent_id = agent.id;
      }
    }

    if (!orgId) {
      console.warn('[voice/webhook] Could not resolve org from agent_id:', agentId);
      // Still return 200 to avoid retries — log and move on
      return NextResponse.json({ received: true });
    }

    // Upsert the call record
    const { error } = await supabase.from('calls').upsert({
      ...callData,
      org_id: orgId,
    }, { onConflict: 'provider_call_id' });

    if (error) {
      console.error('[voice/webhook] DB upsert error:', error);
      return NextResponse.json({ error: 'Database error' }, { status: 500 });
    }

    // TODO: send SMS alert to org owner if is_emergency is true
    // const actionItems = callData.action_items;
    // if (actionItems?.is_emergency) await sendEmergencySMS(orgId, callData);

    return NextResponse.json({ processed: true });
  } catch (error: any) {
    console.error('[voice/webhook] Unexpected error:', error);
    return NextResponse.json({ error: error.message ?? 'Webhook handler failed' }, { status: 400 });
  }
}
