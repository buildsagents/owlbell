import { FASTAPI_V1 } from "@/lib/consolidation";
import type { AuditIntakeDraft } from "@/lib/onboarding-storage";

export async function saveDraftRemote(
  draft: AuditIntakeDraft,
  draftId?: string,
): Promise<string | null> {
  try {
    const res = await fetch(`${FASTAPI_V1}/onboarding/draft`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        ...draft,
        step: 0,
        draftId,
      }),
    });
    const json = await res.json();
    if (!res.ok || !json.ok) return draftId ?? null;
    return json.draft_id as string;
  } catch {
    return draftId ?? null;
  }
}

export async function loadDraftRemote(
  opts: { draftId?: string; email?: string },
): Promise<{ draft: AuditIntakeDraft; draftId: string } | null> {
  try {
    const params = new URLSearchParams();
    if (opts.draftId) params.set("draft_id", opts.draftId);
    else if (opts.email) params.set("email", opts.email);
    else return null;

    const res = await fetch(`${FASTAPI_V1}/onboarding/draft?${params}`);
    const json = await res.json();
    if (!res.ok || !json.ok || !json.found) return null;

    const payload = json.draft.payload as AuditIntakeDraft;
    return {
      draft: payload,
      draftId: json.draft.draft_id,
    };
  } catch {
    return null;
  }
}