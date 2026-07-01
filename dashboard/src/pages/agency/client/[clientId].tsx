import { useParams, useNavigate } from "react-router-dom";
import { useAgencyClient, useAdvanceOnboarding } from "@/hooks/use-agency";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { EmptyState } from "@/components/shared/empty-state";
import { Skeleton, SkeletonCard } from "@/components/shared/skeleton";
import { cn, formatDate, formatPhoneNumber } from "@/lib/utils";
import {
  Building2, Phone, Mail, Globe, Clock, CheckCircle2, Circle, ArrowLeft, Zap, TrendingUp
} from "lucide-react";

const statusColors: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-700",
  trial: "bg-blue-100 text-blue-700",
  paused: "bg-amber-100 text-amber-700",
  suspended: "bg-rose-100 text-rose-700",
};

export default function ClientDetailPage() {
  const { clientId } = useParams<{ clientId: string }>();
  const navigate = useNavigate();
  const { data: client, isLoading } = useAgencyClient(clientId!);
  const advanceOnboarding = useAdvanceOnboarding();

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="mb-6">
          <Skeleton className="mb-1 h-7 w-48" />
          <Skeleton className="h-4 w-64" />
        </div>
        <div className="grid gap-6 lg:grid-cols-3">
          <SkeletonCard className="lg:col-span-2" />
          <SkeletonCard />
        </div>
        <SkeletonCard />
        <div className="grid gap-6 lg:grid-cols-2">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      </div>
    );
  }
  if (!client) return <EmptyState title="Client not found" illustration="clients" />;

  const completedSteps = client.onboarding.filter((s) => s.completed).length;
  const totalSteps = client.onboarding.length;
  const progressPct = totalSteps > 0 ? Math.round((completedSteps / totalSteps) * 100) : 0;

  const handleAdvance = () => {
    if (clientId) advanceOnboarding.mutate(clientId);
  };

  return (
    <div className="space-y-6">
      <PageHeader title={client.name} description={`Client since ${client.createdAt ? formatDate(client.createdAt) : "N/A"}`}>
        <Button variant="ghost" onClick={() => navigate("/agency/clients")}>
          <ArrowLeft className="mr-1 h-4 w-4" /> Back
        </Button>
      </PageHeader>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Client Info</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-blue-50 p-2">
                  <Building2 className="h-4 w-4 text-blue-500" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Industry</p>
                  <p className="font-medium">{client.industry ?? "N/A"}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-purple-50 p-2">
                  <Globe className="h-4 w-4 text-purple-500" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Plan</p>
                  <p className="font-medium capitalize">{client.plan}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-emerald-50 p-2">
                  <Phone className="h-4 w-4 text-emerald-500" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Phone</p>
                  <p className="font-medium">{client.phone ? formatPhoneNumber(client.phone) : "N/A"}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-amber-50 p-2">
                  <Mail className="h-4 w-4 text-amber-500" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Email</p>
                  <p className="font-medium">{client.email ?? "N/A"}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-rose-50 p-2">
                  <Clock className="h-4 w-4 text-rose-500" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Timezone</p>
                  <p className="font-medium">{client.timezone ?? "N/A"}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-indigo-50 p-2">
                  <Badge className={statusColors[client.status] ?? ""}>{client.status}</Badge>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Status</p>
                  <p className="font-medium capitalize">{client.status}</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
            <CardDescription>Manage this client.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Button
              className="w-full justify-start"
              variant="outline"
              onClick={handleAdvance}
              disabled={advanceOnboarding.isPending}
            >
              <Zap className="mr-2 h-4 w-4" />
              {advanceOnboarding.isPending ? "Advancing..." : "Advance Onboarding"}
            </Button>
            <Button
              className="w-full justify-start"
              variant="outline"
              onClick={() => navigate(`/calls?tenant=${client.id}`)}
            >
              <Phone className="mr-2 h-4 w-4" />
              View Calls
            </Button>
            <Button
              className="w-full justify-start"
              variant="outline"
              onClick={() => navigate(`/analytics?tenant=${client.id}`)}
            >
              <TrendingUp className="mr-2 h-4 w-4" />
              Analytics
            </Button>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Onboarding Progress</CardTitle>
          <CardDescription>
            {completedSteps} of {totalSteps} steps completed ({progressPct}%)
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Progress value={progressPct} className="mb-6" />
          <div className="space-y-3">
            {client.onboarding.map((step) => (
              <div
                key={step.step}
                className={cn(
                  "flex items-start gap-3 rounded-lg border p-3",
                  step.completed && "border-emerald-200 bg-emerald-50/50"
                )}
              >
                {step.completed ? (
                  <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-500" />
                ) : (
                  <Circle className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" />
                )}
                <div>
                  <p className={cn("font-medium", step.completed && "text-emerald-700")}>
                    {step.name}
                  </p>
                  <p className="text-xs text-muted-foreground">{step.description}</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Recent Calls</CardTitle>
            <CardDescription>Calls this month: {client.callsThisMonth}</CardDescription>
          </CardHeader>
          <CardContent>
            <EmptyState
              title="No calls data"
              description="Call data will appear once calls are routed."
              illustration="calls"
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Performance</CardTitle>
            <CardDescription>Key metrics at a glance.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between rounded-lg border p-3">
                <span className="text-sm text-muted-foreground">Avg Answer Time</span>
                <span className="font-medium">
                  {client.avgAnswerTime ? `${client.avgAnswerTime.toFixed(0)}s` : "N/A"}
                </span>
              </div>
              <div className="flex items-center justify-between rounded-lg border p-3">
                <span className="text-sm text-muted-foreground">Booking Rate</span>
                <span className="font-medium">
                  {client.bookingRate ? `${(client.bookingRate * 100).toFixed(1)}%` : "N/A"}
                </span>
              </div>
              <div className="flex items-center justify-between rounded-lg border p-3">
                <span className="text-sm text-muted-foreground">MTD Revenue</span>
                <span className="font-medium">${client.revenueMtd.toFixed(2)}</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
