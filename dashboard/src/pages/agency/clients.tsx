import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAgencyClients } from "@/hooks/use-agency";
import { PageHeader } from "@/components/layout/PageHeader";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { LoadingSpinner } from "@/components/shared/loading-spinner";
import { EmptyState } from "@/components/shared/empty-state";
import { useDebounce } from "@/hooks/use-debounce";
import { formatPhoneNumber } from "@/lib/utils";
import { Building2, Search, UserPlus } from "lucide-react";

const statusColors: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-700",
  trial: "bg-blue-100 text-blue-700",
  paused: "bg-amber-100 text-amber-700",
  suspended: "bg-rose-100 text-rose-700",
};

export default function AgencyClientsPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounce(search, 300);
  const { data: clients, isLoading } = useAgencyClients({ search: debouncedSearch || undefined });

  return (
    <div className="space-y-6">
      <PageHeader title="Clients" description="Manage all client tenants">
        <Button onClick={() => navigate("/agency/provision")}>
          <UserPlus className="mr-1 h-4 w-4" /> New Client
        </Button>
      </PageHeader>

      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search clients..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-9"
        />
      </div>

      {isLoading ? (
        <LoadingSpinner />
      ) : clients && clients.length > 0 ? (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Industry</TableHead>
                <TableHead>Plan</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Phone</TableHead>
                <TableHead className="text-right">Calls/Month</TableHead>
                <TableHead className="text-right">Onboarding</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {clients.map((client) => (
                <TableRow
                  key={client.id}
                  className="cursor-pointer"
                  onClick={() => navigate(`/agency/client/${client.id}`)}
                >
                  <TableCell className="font-medium">{client.name}</TableCell>
                  <TableCell className="text-muted-foreground">{client.industry ?? "—"}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className="capitalize">{client.plan}</Badge>
                  </TableCell>
                  <TableCell>
                    <Badge className={statusColors[client.status] ?? "bg-muted text-muted-foreground"}>
                      {client.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {client.phone ? formatPhoneNumber(client.phone) : "—"}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{client.callsThisMonth}</TableCell>
                  <TableCell className="text-right">
                    {client.onboardingComplete ? (
                      <Badge className="bg-emerald-100 text-emerald-700">Complete</Badge>
                    ) : (
                      <span className="text-sm text-muted-foreground">Step {client.onboardingStep}/8</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        navigate(`/agency/client/${client.id}`);
                      }}
                    >
                      View
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : (
        <EmptyState
          title="No clients found"
          description={search ? "Try a different search term." : "Provision your first client to get started."}
          icon={Building2}
        >
          <Button onClick={() => navigate("/agency/provision")}>
            <UserPlus className="mr-1 h-4 w-4" /> New Client
          </Button>
        </EmptyState>
      )}
    </div>
  );
}
