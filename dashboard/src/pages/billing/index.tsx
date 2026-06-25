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

  const meters = usage ? [
    { label: "Calls", used: usage.callsUsed, limit: usage.callsLimit, icon: Phone, color: "bg-emerald-500" },
    { label: "Minutes", used: usage.minutesUsed, limit: usage.minutesLimit, icon: Clock, color: "bg-blue-500" },
    { label: "Team Members", used: usage.teamMembersUsed, limit: usage.teamMembersLimit, icon: Users, color: "bg-purple-500" },
    { label: "Integrations", used: usage.integrationsUsed, limit: usage.integrationsLimit, icon: Puzzle, color: "bg-amber-500" },
  ] : [];

  return (
    <div className="space-y-6">
      <PageHeader title="Billing" description="Monitor your usage and plan" />

      {/* Current Plan */}
      <div className="rounded-lg border bg-card p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">Current Plan</p>
            <h2 className="text-2xl font-bold">{plan?.displayName || "Free"}</h2>
            <p className="text-sm text-muted-foreground">{plan?.description}</p>
          </div>
          <div className="text-right">
            <p className="text-3xl font-bold">${plan?.price || 0}<span className="text-sm font-normal text-muted-foreground">/mo</span></p>
            {tenant?.plan !== "enterprise" && (
              <Button size="sm" className="mt-2">Upgrade</Button>
            )}
          </div>
        </div>
        {plan && (
          <div className="mt-4 flex flex-wrap gap-2">
            {plan.features.map((f) => (
              <Badge key={f} variant="secondary" className="flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3 text-emerald-500" /> {f}
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
                  <div className={cn("flex h-8 w-8 items-center justify-center rounded-lg", meter.color.replace("bg-", "bg-opacity-10 bg-"))}>
                    <Icon className={cn("h-4 w-4", meter.color.replace("bg-", "text-"))} />
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
