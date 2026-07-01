import { useAuthStore } from "@/stores/auth-store";
import { useBillingUsage } from "@/hooks/use-billing";
import { PageHeader } from "@/components/layout/PageHeader";
import { LoadingSpinner } from "@/components/shared/loading-spinner";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn, formatNumber } from "@/lib/utils";
import { PLANS } from "@/types/billing";
import { Phone, Clock, Users, Puzzle, CheckCircle2 } from "lucide-react";

export default function BillingPage() {
  const tenant = useAuthStore((s) => s.tenant);
  const { data: usage, isLoading } = useBillingUsage();
  const plan = tenant?.plan ? PLANS[tenant.plan] : null;

  const toneClasses = {
    primary: { chip: "bg-primary/10", icon: "text-primary" },
    info: { chip: "bg-info/10", icon: "text-info" },
    "brand-accent": { chip: "bg-brand-accent/15", icon: "text-brand-accent" },
    warning: { chip: "bg-warning/10", icon: "text-warning" },
  } as const;

  const meters = usage ? [
    { label: "Calls", used: usage.callsUsed, limit: usage.callsLimit, icon: Phone, tone: "primary" },
    { label: "Minutes", used: usage.minutesUsed, limit: usage.minutesLimit, icon: Clock, tone: "info" },
    { label: "Team Members", used: usage.teamMembersUsed, limit: usage.teamMembersLimit, icon: Users, tone: "brand-accent" },
    { label: "Integrations", used: usage.integrationsUsed, limit: usage.integrationsLimit, icon: Puzzle, tone: "warning" },
  ] as const : [];

  return (
    <div className="space-y-6">
      <PageHeader title="Billing" description="Monitor your usage and plan" />

      {/* Current Plan */}
      <div className="relative overflow-hidden rounded-xl border bg-gradient-to-br from-primary via-primary to-[hsl(243,70%,42%)] p-6 text-white shadow-sm">
        <div className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full bg-brand-accent/20 blur-3xl" />
        <div className="relative flex items-center justify-between">
          <div>
            <p className="text-sm text-white/70">Current Plan</p>
            <h2 className="text-2xl font-bold">{plan?.displayName || "Free"}</h2>
            <p className="text-sm text-white/70">{plan?.description}</p>
          </div>
          <div className="text-right">
            <p className="text-3xl font-bold">${plan?.price || 0}<span className="text-sm font-normal text-white/70">/mo</span></p>
            {tenant?.plan !== "enterprise" && (
              <Button size="sm" className="mt-2 bg-brand-accent text-brand-accent-foreground hover:bg-brand-accent/90">Upgrade</Button>
            )}
          </div>
        </div>
        {plan && (
          <div className="relative mt-4 flex flex-wrap gap-2">
            {plan.features.map((f) => (
              <Badge key={f} variant="secondary" className="flex items-center gap-1 border-transparent bg-white/15 text-white">
                <CheckCircle2 className="h-3 w-3 text-brand-accent" /> {f}
              </Badge>
            ))}
          </div>
        )}
      </div>

      {/* Usage Meters */}
      {isLoading ? <LoadingSpinner /> : usage ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {meters.map((meter) => {
            const Icon = meter.icon;
            const pct = meter.limit > 0 ? Math.min(100, (meter.used / meter.limit) * 100) : 0;
            const unlimited = meter.limit === -1;

            return (
              <div key={meter.label} className="rounded-lg border bg-card p-4">
                <div className="flex items-center gap-2 mb-3">
                  <div className={cn("flex h-8 w-8 items-center justify-center rounded-lg", toneClasses[meter.tone].chip)}>
                    <Icon className={cn("h-4 w-4", toneClasses[meter.tone].icon)} />
                  </div>
                  <span className="font-medium">{meter.label}</span>
                </div>
                <div className="flex items-end justify-between mb-2">
                  <span className="text-2xl font-bold tabular-nums">{formatNumber(meter.used)}</span>
                  <span className="text-sm text-muted-foreground">
                    {unlimited ? "Unlimited" : `of ${formatNumber(meter.limit)}`}
                  </span>
                </div>
                {!unlimited && <Progress value={pct} className="h-2" />}
              </div>
            );
          })}
        </div>
      ) : null}

      {/* Plan Comparison */}
      <div className="rounded-lg border bg-card">
        <div className="border-b p-4">
          <h3 className="font-semibold">Compare Plans</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                <th className="p-3 text-left font-medium">Feature</th>
                {Object.values(PLANS).map((p) => (
                  <th key={p.id} className={cn("p-3 text-center font-medium", p.id === tenant?.plan && "bg-primary/5")}>
                    {p.displayName}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[
                { label: "Monthly Calls", key: "monthlyCalls" },
                { label: "Monthly Minutes", key: "monthlyMinutes" },
                { label: "Team Members", key: "teamMembers" },
                { label: "Integrations", key: "integrations" },
                { label: "Price/mo", key: "price", format: (v: number) => v === 0 ? "Free" : `$${v}` },
              ].map((row) => (
                <tr key={row.key} className="border-b">
                  <td className="p-3 font-medium">{row.label}</td>
                  {Object.values(PLANS).map((p) => (
                    <td key={p.id} className={cn("p-3 text-center", p.id === tenant?.plan && "bg-primary/5")}>
                      {row.format
                        ? row.format(p[row.key as keyof typeof p] as number)
                        : (p[row.key as keyof typeof p] as number) === -1 ? "Unlimited" : formatNumber(p[row.key as keyof typeof p] as number)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
