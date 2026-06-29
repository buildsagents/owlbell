import { FASTAPI_V1 } from "@/lib/consolidation";
import type { OnboardingDraft } from "@/lib/onboarding-storage";

export async function saveDraftRemote(
  draft: OnboardingDraft,
  draftId?: string,
): Promise<string | null> {
  try {
    const res = await fetch(`${FASTAPI_V1}/onboarding/draft`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        ...draft,
        step: draft.step,
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
): Promise<{ draft: OnboardingDraft; draftId: string; step: number } | null> {
  try {
    const params = new URLSearchParams();
    if (opts.draftId) params.set("draft_id", opts.draftId);
    else if (opts.email) params.set("email", opts.email);
    else return null;

    const res = await fetch(`${FASTAPI_V1}/onboarding/draft?${params}`);
    const json = await res.json();
    if (!res.ok || !json.ok || !json.found) return null;

    const payload = json.draft.payload as OnboardingDraft;
    return {
      draft: { ...payload, step: json.draft.step },
      draftId: json.draft.draft_id,
      step: json.draft.step,
    };
  } catch {
    return null;
  }
}