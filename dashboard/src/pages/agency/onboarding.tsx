import { useNavigate } from "react-router-dom";
import { useOnboardingPipeline } from "@/hooks/use-agency";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton, SkeletonKanbanColumn } from "@/components/shared/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { cn } from "@/lib/utils";
import { CheckCircle2, Circle, ClipboardCheck, PhoneCall, Rocket, ShieldCheck } from "lucide-react";

const COLUMN_NAMES = [
  "Intake",
  "Voice Build",
  "Knowledge",
  "Routing",
  "QA Review",
  "Live",
];

const COLUMN_STEP_RANGES: [number, number][] = [
  [0, 0],
  [1, 2],
  [3, 3],
  [4, 4],
  [5, 6],
  [7, 8],
];

function getColumnIndex(step: number, complete: boolean): number {
  if (complete) return 5;
  for (let i = 0; i < COLUMN_STEP_RANGES.length; i++) {
    const [min, max] = COLUMN_STEP_RANGES[i];
    if (step >= min && step <= max) return i;
  }
  return 0;
}

export default function OnboardingPipelinePage() {
  const navigate = useNavigate();
  const { data: pipeline, isLoading } = useOnboardingPipeline();

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <Skeleton className="mb-1 h-7 w-64" />
          <Skeleton className="h-4 w-48" />
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonKanbanColumn key={i} cards={2} />
          ))}
        </div>
      </div>
    );
  }
  if (!pipeline)
    return <EmptyState title="No pipeline data" description="Client onboarding data will appear here." illustration="onboarding" />;

  const columns = COLUMN_NAMES.map((name, idx) => ({
    name,
    items: pipeline.clients.filter((c) => getColumnIndex(c.currentStep, c.complete) === idx),
  }));

  return (
    <div className="space-y-6">
      <PageHeader title="Launch Pipeline" description="Move every client from intake to live without skipping voice QA.">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span>{pipeline.clients.length} clients in pipeline</span>
        </div>
      </PageHeader>

      <section className="grid gap-4 md:grid-cols-3">
        <div className="rounded-lg border bg-card p-4">
          <ClipboardCheck className="mb-3 h-5 w-5 text-primary" />
          <p className="font-medium">Complete the brief first</p>
          <p className="mt-1 text-sm text-muted-foreground">Services, pricing guardrails, owner escalation, and booking rules drive the prompt.</p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <PhoneCall className="mb-3 h-5 w-5 text-primary" />
          <p className="font-medium">Listen before launch</p>
          <p className="mt-1 text-sm text-muted-foreground">Every client needs a QA call that checks tone, interruptions, and emergency triage.</p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <ShieldCheck className="mb-3 h-5 w-5 text-primary" />
          <p className="font-medium">Escalation must be real</p>
          <p className="mt-1 text-sm text-muted-foreground">No live account should route urgent callers without a confirmed human fallback.</p>
        </div>
      </section>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-6">
        {columns.map((col) => (
          <div key={col.name} className="space-y-3">
            <div className="flex items-center justify-between rounded-lg bg-muted px-3 py-2">
              <h3 className="text-sm font-semibold">{col.name}</h3>
              <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-primary/10 px-1.5 text-xs font-medium text-primary">
                {col.items.length}
              </span>
            </div>
            <div className="space-y-2">
              {col.items.map((client) => (
                <Card
                  key={client.clientId}
                  className="cursor-pointer transition-colors hover:bg-accent"
                  onClick={() => navigate(`/agency/client/${client.clientId}`)}
                >
                  <CardContent className="p-3">
                    <div className="flex items-start justify-between">
                      <p className="text-sm font-medium leading-tight">{client.name}</p>
                      {client.complete ? (
                        <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" />
                      ) : (
                        <Circle className="h-4 w-4 shrink-0 text-muted-foreground" />
                      )}
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {client.currentStepName}
                    </p>
                    {!client.complete && (
                      <div className="mt-2">
                        <div className="flex items-center gap-1">
                          <div className="h-1 flex-1 overflow-hidden rounded-full bg-muted">
                            <div
                              className={cn(
                                "h-full rounded-full bg-primary transition-all",
                              )}
                              style={{
                                width: `${(client.currentStep / client.totalSteps) * 100}%`,
                              }}
                            />
                          </div>
                          <span className="text-[10px] text-muted-foreground">
                            {client.currentStep}/{client.totalSteps}
                          </span>
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        ))}
      </div>

      {pipeline.clients.length === 0 && (
        <EmptyState title="No clients in pipeline" description="Provision a client to see them here." illustration="onboarding" />
      )}

      <Card>
        <CardContent className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <div className="rounded-lg bg-primary/10 p-2 text-primary">
              <Rocket className="h-5 w-5" />
            </div>
            <div>
              <p className="font-medium">Launch rule</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Mark a client live only after a clean test call, working SMS handoff, and client-approved greeting.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
