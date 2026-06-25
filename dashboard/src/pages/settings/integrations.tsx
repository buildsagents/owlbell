import { useIntegrations } from "@/hooks/use-integrations";
import { PageHeader } from "@/components/layout/PageHeader";
import { LoadingSpinner } from "@/components/shared/loading-spinner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { INTEGRATION_PROVIDERS } from "@/types/integration";
import {
  Calendar,
  MessageSquare,
  Database,
  Zap,
  Webhook,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Plug,
  ExternalLink,
} from "lucide-react";

const providerIcons: Record<string, React.ComponentType<{className?: string}>> = {
  calendar: Calendar,
  "message-square": MessageSquare,
  database: Database,
  zap: Zap,
  webhook: Webhook,
};

export default function IntegrationsPage() {
  const { data: integrations, isLoading } = useIntegrations();

  const getStatus = (provider: string) => {
    const integration = integrations?.find((i) => i.provider === provider);
    return integration?.status || "disconnected";
  };

  const statusConfig: Record<string, { label: string; icon: React.ComponentType<{className?: string}>; color: string; bg: string }> = {
    connected: { label: "Connected", icon: CheckCircle2, color: "text-emerald-500", bg: "bg-emerald-50" },
    disconnected: { label: "Disconnected", icon: XCircle, color: "text-muted-foreground", bg: "bg-muted" },
    error: { label: "Error", icon: AlertCircle, color: "text-rose-500", bg: "bg-rose-50" },
    pending: { label: "Pending", icon: AlertCircle, color: "text-amber-500", bg: "bg-amber-50" },
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Integrations" description="Connect third-party services to your AI" />

      {isLoading ? <LoadingSpinner /> : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {INTEGRATION_PROVIDERS.map((provider) => {
            const status = getStatus(provider.provider);
            const config = statusConfig[status];
            const StatusIcon = config.icon;
            const Icon = providerIcons[provider.icon] || Plug;

            return (
              <div key={provider.provider} className="rounded-lg border bg-card p-5">
                <div className="flex items-start justify-between">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                    <Icon className="h-5 w-5 text-primary" />
                  </div>
                  <Badge className={cn(config.color.replace("text-", "bg-").replace("500", "100"), config.color)}>
                    <StatusIcon className="mr-1 h-3 w-3" /> {config.label}
                  </Badge>
                </div>
                <h3 className="mt-3 font-semibold">{provider.displayName}</h3>
                <p className="text-sm text-muted-foreground">{provider.description}</p>
                <div className="mt-3">
                  <p className="text-xs font-medium text-muted-foreground mb-1">Features:</p>
                  <ul className="space-y-1">
                    {provider.features.map((f) => (
                      <li key={f} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                        <CheckCircle2 className="h-3 w-3 text-emerald-500" /> {f}
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="mt-4">
                  {status === "connected" ? (
                    <Button variant="outline" size="sm" className="w-full">
                      Disconnect
                    </Button>
                  ) : (
                    <Button size="sm" className="w-full" onClick={() => {
                      if (provider.oauthUrl) {
                        window.location.href = provider.oauthUrl;
                      }
                    }}>
                      <ExternalLink className="mr-1 h-4 w-4" /> Connect
                    </Button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
