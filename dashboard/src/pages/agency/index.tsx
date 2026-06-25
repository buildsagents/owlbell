import { useNavigate } from "react-router-dom";
import { useAgencyOverview, useAgencyClients, useOnboardingPipeline } from "@/hooks/use-agency";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { LoadingSpinner } from "@/components/shared/loading-spinner";
import { EmptyState } from "@/components/shared/empty-state";
import { Building2, Phone, CreditCard, Users, TrendingUp, ArrowRight } from "lucide-react";

export default function AgencyOverviewPage() {
  const navigate = useNavigate();
  const { data: overview, isLoading } = useAgencyOverview();
  const { data: clients } = useAgencyClients();
  const { data: pipeline } = useOnboardingPipeline();

  if (isLoading) return <LoadingSpinner />;

  const stats = [
    {
      label: "Total Clients",
      value: overview?.totalClients ?? 0,
      icon: Building2,
      color: "text-blue-500",
      bg: "bg-blue-50",
    },
    {
      label: "Active Clients",
      value: overview?.activeClients ?? 0,
      icon: Users,
      color: "text-emerald-500",
      bg: "bg-emerald-50",
    },
    {
      label: "Calls This Month",
      value: overview?.totalCallsThisMonth ?? 0,
      icon: Phone,
      color: "text-amber-500",
      bg: "bg-amber-50",
    },
    {
      label: "Monthly Revenue",
      value: `$${overview?.mrr?.toLocaleString() ?? 0}`,
      icon: CreditCard,
      color: "text-purple-500",
      bg: "bg-purple-50",
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="Agency Dashboard" description="Multi-tenant management overview">
        <Button onClick={() => navigate("/agency/clients")}>
          <Users className="mr-1 h-4 w-4" /> View Clients
        </Button>
        <Button onClick={() => navigate("/agency/provision")}>
          <Building2 className="mr-1 h-4 w-4" /> New Client
        </Button>
      </PageHeader>

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
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg">Recent Clients</CardTitle>
            <Button variant="ghost" size="sm" onClick={() => navigate("/agency/clients")}>
              View all <ArrowRight className="ml-1 h-3 w-3" />
            </Button>
          </CardHeader>
          <CardContent>
            {clients && clients.length > 0 ? (
              <div className="space-y-3">
                {clients.slice(0, 5).map((client) => (
                  <div
                    key={client.id}
                    className="flex items-center justify-between rounded-lg border p-3 transition-colors hover:bg-accent cursor-pointer"
                    onClick={() => navigate(`/agency/client/${client.id}`)}
                  >
                    <div>
                      <p className="font-medium">{client.name}</p>
                      <p className="text-xs text-muted-foreground">{client.industry ?? "N/A"}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={client.status === "active" ? "default" : "secondary"}>
                        {client.status}
                      </Badge>
                      <span className="text-sm text-muted-foreground">{client.callsThisMonth} calls</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No clients yet" description="Provision your first client to get started." icon={Building2} />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg">Onboarding Pipeline</CardTitle>
            <Button variant="ghost" size="sm" onClick={() => navigate("/agency/onboarding")}>
              View pipeline <ArrowRight className="ml-1 h-3 w-3" />
            </Button>
          </CardHeader>
          <CardContent>
            {pipeline?.clients && pipeline.clients.length > 0 ? (
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
                    <Badge variant={client.complete ? "default" : "outline"}>
                      {client.complete ? "Complete" : `Step ${client.currentStep}/${client.totalSteps}`}
                    </Badge>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No onboarding" description="New client onboarding will appear here." icon={TrendingUp} />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
