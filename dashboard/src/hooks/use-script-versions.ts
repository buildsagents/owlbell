import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ScriptVersion } from "@/components/editors/ScriptEditor";

export type ScriptVersionsMode = "server" | "demo";

const VERSION_PREFIX = "owlbell_script_versions_";

export function loadDemoScriptVersions(storageKey: string): ScriptVersion[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(VERSION_PREFIX + storageKey);
    return raw ? (JSON.parse(raw) as ScriptVersion[]) : [];
  } catch {
    return [];
  }
}

export function persistDemoScriptVersions(storageKey: string, versions: ScriptVersion[]): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(VERSION_PREFIX + storageKey, JSON.stringify(versions.slice(0, 12)));
}

function toScriptVersion(row: Record<string, unknown>): ScriptVersion {
  return {
    id: String(row.id),
    label: String(row.label ?? "v1"),
    content: String(row.content ?? ""),
    savedAt: String(row.savedAt ?? row.saved_at ?? new Date().toISOString()),
  };
}

export function useScriptVersions(
  scriptKey: string,
  options?: { mode?: ScriptVersionsMode },
) {
  const mode = options?.mode ?? "server";

  return useQuery<ScriptVersion[]>({
    queryKey: ["script-versions", mode, scriptKey],
    queryFn: async () => {
      if (mode === "demo") {
        return loadDemoScriptVersions(scriptKey);
      }
      const response = await api.get<Record<string, unknown>[]>(
        `/business/scripts/${encodeURIComponent(scriptKey)}/versions`,
      );
      const rows = Array.isArray(response.data) ? response.data : [];
      return rows.map((row) => toScriptVersion(row));
    },
    staleTime: mode === "demo" ? Infinity : 60_000,
  });
}

export function useSaveScriptVersion(
  scriptKey: string,
  options?: { mode?: ScriptVersionsMode },
) {
  const mode = options?.mode ?? "server";
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: { content: string; label?: string }) => {
      if (mode === "demo") {
        const existing = loadDemoScriptVersions(scriptKey);
        const entry: ScriptVersion = {
          id: crypto.randomUUID(),
          label: payload.label ?? `v${existing.length + 1}`,
          content: payload.content,
          savedAt: new Date().toISOString(),
        };
        const next = [entry, ...existing].slice(0, 12);
        persistDemoScriptVersions(scriptKey, next);
        return entry;
      }
      const response = await api.post<Record<string, unknown>>(
        `/business/scripts/${encodeURIComponent(scriptKey)}/versions`,
        payload,
      );
      return toScriptVersion(response.data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["script-versions", mode, scriptKey] });
    },
  });
}