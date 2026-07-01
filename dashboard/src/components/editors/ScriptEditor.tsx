import { useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { History, RotateCcw } from "lucide-react";
import {
  useSaveScriptVersion,
  useScriptVersions,
  type ScriptVersionsMode,
} from "@/hooks/use-script-versions";
import { toast } from "sonner";

export type ScriptVersion = {
  id: string;
  label: string;
  content: string;
  savedAt: string;
};

type Props = {
  value: string;
  onChange: (value: string) => void;
  label: string;
  placeholder?: string;
  maxLength?: number;
  rows?: number;
  storageKey: string;
  mode?: ScriptVersionsMode;
};

export function ScriptEditor({
  value,
  onChange,
  label,
  placeholder,
  maxLength = 2000,
  rows = 5,
  storageKey,
  mode = "server",
}: Props) {
  const { data: versions = [], isError, error } = useScriptVersions(storageKey, { mode });
  const saveVersionMutation = useSaveScriptVersion(storageKey, { mode });

  const previewHtml = useMemo(() => {
    if (!value.trim()) return "<p class='text-muted-foreground'>Nothing to preview yet.</p>";
    return value
      .split("\n")
      .map((line) => `<p>${line.replace(/</g, "&lt;") || "&nbsp;"}</p>`)
      .join("");
  }, [value]);

  const saveVersion = async () => {
    try {
      await saveVersionMutation.mutateAsync({ content: value });
      toast.success(
        mode === "demo" ? "Version saved in demo workspace" : "Version saved to your account",
      );
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 401 || status === 403) {
        toast.error("Sign in required", {
          description: "Version history syncs across devices only when you are signed in.",
        });
        return;
      }
      toast.error("Could not save version", {
        description:
          error instanceof Error
            ? error.message
            : "Server unreachable. Retry when your connection is restored.",
      });
    }
  };

  const restore = (content: string) => {
    onChange(content);
  };

  return (
    <div className="space-y-3 rounded-lg border p-4">
      {mode === "demo" && (
        <p className="rounded-md border border-dashed border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100">
          Demo workspace - sign in to sync version history across devices.
        </p>
      )}
      {mode === "server" && isError && (
        <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          Could not load version history from the server. Saving requires a working connection.
        </p>
      )}

      <div className="flex items-center justify-between gap-2">
        <label className="text-sm font-medium">{label}</label>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={saveVersion}
          disabled={saveVersionMutation.isPending || (mode === "server" && isError)}
        >
          <History className="mr-1 h-4 w-4" /> Save version
        </Button>
      </div>

      <Tabs defaultValue="edit">
        <TabsList>
          <TabsTrigger value="edit">Edit</TabsTrigger>
          <TabsTrigger value="preview">Preview</TabsTrigger>
        </TabsList>
        <TabsContent value="edit">
          <Textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            maxLength={maxLength}
            rows={rows}
            className="font-mono text-sm"
          />
          <p className="mt-1 text-xs text-muted-foreground text-right">
            {value.length}/{maxLength}
          </p>
        </TabsContent>
        <TabsContent value="preview">
          <div
            className="prose prose-sm max-w-none rounded-md border bg-muted/30 p-3 min-h-[120px]"
            dangerouslySetInnerHTML={{ __html: previewHtml }}
          />
        </TabsContent>
      </Tabs>

      {versions.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase text-muted-foreground">
            Version history ({mode === "demo" ? "demo workspace" : "synced to account"})
          </p>
          {mode === "server" && (
            <p className="text-xs text-muted-foreground">
              Saved versions persist in your tenant settings. Knowledge-base RAG re-indexing is
              queued on save in production.
            </p>
          )}
          <ul className="space-y-1">
            {versions.map((v) => (
              <li key={v.id} className="flex items-center justify-between gap-2 text-sm">
                <span>
                  {v.label} / {new Date(v.savedAt).toLocaleString()}
                </span>
                <Button type="button" variant="ghost" size="sm" onClick={() => restore(v.content)}>
                  <RotateCcw className="mr-1 h-3 w-3" /> Restore
                </Button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
