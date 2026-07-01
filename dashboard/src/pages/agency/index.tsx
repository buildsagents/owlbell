import { useNavigate } from "react-router-dom";
import { useAgencyOverview, useAgencyClients, useOnboardingPipeline } from "@/hooks/use-agency";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SkeletonStatsGrid, SkeletonTableRow } from "@/components/shared/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import {
  ArrowRight,
  Building2,
  CheckCircle2,
  ClipboardCheck,
  CreditCard,
  Phone,
  Rocket,
  TrendingUp,
  UserPlus,
  Users,
} from "lucide-react";

export default function AgencyOverviewPage() {
  const navigate = useNavigate();
  const { data: overview, isLoading } = useAgencyOverview();
  const { data: clients, isLoading: clientsLoading } = useAgencyClients();
  const { data: pipeline, isLoading: pipelineLoading } = useOnboardingPipeline();

  const stats = [
    {
      label: "Total Clients",
      value: overview?.totalClients ?? 0,
      icon: Building2,
      detail: `${overview?.trialClients ?? 0} trials being converted`,
      color: "text-sky-600",
      bg: "bg-sky-50",
    },
    {
      label: "Active Clients",
      value: overview?.activeClients ?? 0,
      icon: Users,
      detail: "Live and billable",
      color: "text-emerald-600",
      bg: "bg-emerald-50",
    },
    {
      label: "Calls This Month",
      value: (overview?.totalCallsThisMonth ?? 0).toLocaleString(),
      icon: Phone,
      detail: `${overview?.avgCallsPerClient ?? 0} avg/client`,
      color: "text-indigo-600",
      bg: "bg-indigo-50",
    },
    {
      label: "Monthly Revenue",
      value: `$${overview?.mrr?.toLocaleString() ?? 0}`,
      icon: CreditCard,
      detail: `$${overview?.arr?.toLocaleString() ?? 0} annualized`,
      color: "text-rose-600",
      bg: "bg-rose-50",
    },
  ];

  const launchReady = pipeline?.clients.filter((client) => client.complete).length ?? 0;
  const inBuild = pipeline?.clients.filter((client) => !client.complete).length ?? 0;
  const conversionRate = overview?.totalClients
    ? Math.round(((overview.activeClients ?? 0) / overview.totalClients) * 100)
    : 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Agency Command Center"
        description="Client launches, revenue, and live-call operations in one place."
      >
        <Button variant="outline" onClick={() => navigate("/agency/onboarding")}>
          <ClipboardCheck className="mr-1 h-4 w-4" /> Launch Pipeline
        </Button>
        <Button onClick={() => navigate("/agency/provision")}>
          <UserPlus className="mr-1 h-4 w-4" /> New Client
        </Button>
      </PageHeader>

      <section className="relative overflow-hidden rounded-xl border bg-gradient-to-br from-primary via-primary to-[hsl(243,70%,42%)] p-5 text-white shadow-sm">
        <div className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full bg-brand-accent/20 blur-3xl" />
        <div className="relative grid gap-5 lg:grid-cols-[1.4fr_1fr] lg:items-center">
          <div>
            <div className="mb-3 inline-flex items-center gap-2 rounded-md bg-brand-accent/20 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-brand-accent">
              <Rocket className="h-3.5 w-3.5" />
              Agency growth cockpit
            </div>
            <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
              Every client should look launch-ready before the first routed call.
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-white/70">
              Use this board to spot stuck onboarding, prove retained revenue, and keep voice quality reviews tied to booked work.
            </p>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-lg bg-white/10 p-3">
              <p className="text-xs text-slate-300">Conversion</p>
              <p className="mt-1 text-2xl font-bold tabular-nums">{conversionRate}%</p>
            </div>
            <div className="rounded-lg bg-white/10 p-3">
              <p className="text-xs text-slate-300">In build</p>
              <p className="mt-1 text-2xl font-bold tabular-nums">{inBuild}</p>
            </div>
            <div className="rounded-lg bg-white/10 p-3">
              <p className="text-xs text-slate-300">Live</p>
              <p className="mt-1 text-2xl font-bold tabular-nums">{launchReady}</p>
            </div>
          </div>
        </div>
      </section>

      {isLoading ? (
        <SkeletonStatsGrid count={4} />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {stats.map((stat) => {
            const Icon = stat.icon;
            return (
              <Card key={stat.label}>
                <CardContent className="p-6">
                  <div className="flex items-center justify-between">
                    <div className={`rounded-lg p-2 ${stat.bg}`}>
                      <Icon className={`h-5 w-5 ${stat.color}`} />
                    </div>
                  </div>
                  <div className="mt-4">
                    <p className="text-2xl font-bold tabular-nums">{stat.value}</p>
                    <p className="text-sm text-muted-foreground">{stat.label}</p>
                    <p className="mt-2 text-xs text-muted-foreground">{stat.detail}</p>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg">Recent Clients</CardTitle>
            <Button variant="ghost" size="sm" onClick={() => navigate("/agency/clients")}>
              View all <ArrowRight className="ml-1 h-3 w-3" />
            </Button>
          </CardHeader>
          <CardContent>
            {clientsLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 3 }).map((_, i) => <SkeletonTableRow key={i} columns={3} />)}
              </div>
            ) : clients && clients.length > 0 ? (
              <div className="space-y-3">
                {clients.slice(0, 5).map((client) => (
                  <div
                    key={client.id}
                    className="flex items-center justify-between rounded-lg border p-3 transition-colors hover:bg-accent cursor-pointer"
                    onClick={() => navigate(`/agency/client/${client.id}`)}
                  >
                    <div>
                      <p className="font-medium">{client.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {client.industry ?? "N/A"} / ${client.revenueMtd.toLocaleString()} MTD
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={client.status === "active" ? "success" : "warning"} className="capitalize">
                        {client.status}
                      </Badge>
                      <span className="text-sm text-muted-foreground">{client.callsThisMonth} calls</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No clients yet" description="Provision your first client to get started." illustration="clients" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg">Launch Pipeline</CardTitle>
            <Button variant="ghost" size="sm" onClick={() => navigate("/agency/onboarding")}>
              View pipeline <ArrowRight className="ml-1 h-3 w-3" />
            </Button>
          </CardHeader>
          <CardContent>
            {pipelineLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 3 }).map((_, i) => <SkeletonTableRow key={i} columns={2} />)}
              </div>
            ) : pipeline?.clients && pipeline.clients.length > 0 ? (
              <div className="space-y-3">
                {pipeline.clients.slice(0, 5).map((client) => (
                  <div
                    key={client.clientId}
                    className="flex items-center justify-between rounded-lg border p-3 transition-colors hover:bg-accent cursor-pointer"
                    onClick={() => navigate(`/agency/client/${client.clientId}`)}
                  >
                    <div>
                      <p className="font-medium">{client.name}</p>
                      <p className="text-xs text-muted-foreground">{client.currentStepName}</p>
                    </div>
                    <Badge variant={client.complete ? "success" : "brand"}>
                      {client.complete ? (
                        <span className="inline-flex items-center gap-1">
                          <CheckCircle2 className="h-3 w-3" /> Live
                        </span>
                      ) : (
                        `Step ${client.currentStep}/${client.totalSteps}`
                      )}
                    </Badge>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No onboarding" description="New client onboarding will appear here." illustration="onboarding" />
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Next Best Actions</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-3">
          <button
            className="group rounded-lg border p-4 text-left transition-all hover:border-primary/30 hover:shadow-sm"
            onClick={() => navigate("/agency/provision")}
          >
            <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
              <UserPlus className="h-4.5 w-4.5" />
            </div>
            <p className="font-medium">Spin up a client build</p>
            <p className="mt-1 text-sm text-muted-foreground">Create tenant, default voice, routing, and onboarding tasks.</p>
          </button>
          <button
            className="group rounded-lg border p-4 text-left transition-all hover:border-brand-accent/40 hover:shadow-sm"
            onClick={() => navigate("/calls")}
          >
            <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-lg bg-brand-accent/15 text-brand-accent transition-colors group-hover:bg-brand-accent group-hover:text-brand-accent-foreground">
              <Phone className="h-4.5 w-4.5" />
            </div>
            <p className="font-medium">Review live call quality</p>
            <p className="mt-1 text-sm text-muted-foreground">Catch robotic phrases before prospects or clients hear them again.</p>
          </button>
          <button
            className="group rounded-lg border p-4 text-left transition-all hover:border-success/40 hover:shadow-sm"
            onClick={() => navigate("/analytics")}
          >
            <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-lg bg-success/10 text-success transition-colors group-hover:bg-success group-hover:text-success-foreground">
              <TrendingUp className="h-4.5 w-4.5" />
            </div>
            <p className="font-medium">Package proof for sales</p>
            <p className="mt-1 text-sm text-muted-foreground">Turn booked calls, missed-call saves, and response time into client proof.</p>
          </button>
        </CardContent>
      </Card>
    </div>
  );
}
