import { useState } from "react";
import { useLeads, useLeadStats, type Lead } from "@/hooks/use-leads";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Search,
  Mail,
  MessageSquareReply,
  TrendingUp,
  Users,
  Phone,
  Globe,
  Building2,
  MapPin,
  ExternalLink,
  Clock,
  XCircle,
  AlertCircle,
  Send,
} from "lucide-react";

const STATUS_COLORS: Record<string, string> = {
  new: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  sent: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  replied: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300",
  bounced: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  unsubscribed: "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300",
};

const CLASSIFICATION_COLORS: Record<string, string> = {
  interested: "text-emerald-600 font-medium",
  not_interested: "text-slate-500",
  objection: "text-amber-600 font-medium",
  question: "text-blue-600 font-medium",
  unsubscribe: "text-red-600 font-medium",
  neutral: "text-slate-400",
};

function OutcomeTimeline({ outcomes }: { outcomes: Lead["outcomes"] }) {
  if (!outcomes || outcomes.length === 0) {
    return <p className="text-sm text-muted-foreground">No activity yet</p>;
  }
  return (
    <div className="space-y-3">
      {outcomes.map((o, i) => (
        <div key={i} className="flex gap-3 text-sm">
          <div className="flex flex-col items-center">
            <div className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10">
              {o.type === "sent" || o.type === "follow_up" ? (
                <Send className="h-3 w-3 text-blue-600" />
              ) : o.type === "replied" ? (
                <MessageSquareReply className="h-3 w-3 text-emerald-600" />
              ) : o.type === "bounced" ? (
                <XCircle className="h-3 w-3 text-red-600" />
              ) : o.type === "unsubscribed" ? (
                <AlertCircle className="h-3 w-3 text-amber-600" />
              ) : (
                <Clock className="h-3 w-3 text-slate-400" />
              )}
            </div>
            {i < outcomes.length - 1 && <div className="h-full w-px bg-border" />}
          </div>
          <div className="pb-4">
            <p className="font-medium capitalize">{o.type.replace(/_/g, " ")}</p>
            {o.note && <p className="text-muted-foreground text-xs">{o.note}</p>}
            <p className="text-xs text-muted-foreground">
              {new Date(o.timestamp).toLocaleString()}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}

function ReplyThread({ replies }: { replies: Lead["replies"] }) {
  if (!replies || replies.length === 0) {
    return <p className="text-sm text-muted-foreground">No replies received</p>;
  }
  return (
    <div className="space-y-3">
      {replies.map((r, i) => (
        <div key={i} className="rounded-lg border bg-muted/30 p-3">
          <div className="mb-1 flex items-center gap-2">
            <Badge variant="outline" className={CLASSIFICATION_COLORS[r.classification] || ""}>
              {r.classification}
            </Badge>
            <span className="text-xs text-muted-foreground">
              {new Date(r.timestamp).toLocaleString()}
            </span>
          </div>
          <p className="whitespace-pre-wrap text-sm">{r.body}</p>
        </div>
      ))}
    </div>
  );
}

function LeadDetailDialog({
  lead,
  open,
  onOpenChange,
}: {
  lead: Lead;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Building2 className="h-5 w-5 text-muted-foreground" />
            {lead.name}
          </DialogTitle>
          <DialogDescription>
            <span className="flex items-center gap-1">
              <MapPin className="h-3 w-3" />
              {lead.city}, {lead.state} &middot; {lead.trade}
            </span>
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">Email</p>
            <a
              href={`mailto:${lead.email}`}
              className="flex items-center gap-1 text-sm font-medium hover:underline"
            >
              <Mail className="h-3 w-3" />
              {lead.email}
            </a>
          </div>
          {lead.phone && (
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Phone</p>
              <p className="flex items-center gap-1 text-sm font-medium">
                <Phone className="h-3 w-3" />
                {lead.phone}
              </p>
            </div>
          )}
          {lead.website && (
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Website</p>
              <a
                href={lead.website}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-sm font-medium hover:underline"
              >
                <Globe className="h-3 w-3" />
                {new URL(lead.website).hostname}
                <ExternalLink className="h-3 w-3" />
              </a>
            </div>
          )}
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">Status</p>
            <Badge className={STATUS_COLORS[lead.status] || ""}>{lead.status}</Badge>
          </div>
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">Contacted</p>
            <p className="text-sm">
              {lead.contactCount} time{lead.contactCount !== 1 ? "s" : ""}
            </p>
          </div>
          {lead.lastContacted && (
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Last Contacted</p>
              <p className="text-sm">{new Date(lead.lastContacted).toLocaleString()}</p>
            </div>
          )}
        </div>

        <div className="mt-4">
          <h4 className="mb-2 text-sm font-semibold">Activity Timeline</h4>
          <OutcomeTimeline outcomes={lead.outcomes} />
        </div>

        <div className="mt-4">
          <h4 className="mb-2 text-sm font-semibold">Replies</h4>
          <ReplyThread replies={lead.replies} />
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function OutreachPage() {
  const { data: leads, isLoading } = useLeads();
  const { data: stats } = useLeadStats();
  const [search, setSearch] = useState("");
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);

  const filtered = (leads || []).filter(
    (l) =>
      l.name.toLowerCase().includes(search.toLowerCase()) ||
      l.email.toLowerCase().includes(search.toLowerCase()) ||
      l.trade.toLowerCase().includes(search.toLowerCase()) ||
      l.city.toLowerCase().includes(search.toLowerCase())
  );

  const statCards = [
    {
      label: "Total Leads",
      value: stats?.total || 0,
      icon: Users,
      color: "text-blue-600",
      bg: "bg-blue-50 dark:bg-blue-950",
    },
    {
      label: "Emails Sent",
      value: stats?.totalSent || 0,
      icon: Send,
      color: "text-violet-600",
      bg: "bg-violet-50 dark:bg-violet-950",
    },
    {
      label: "Replies",
      value: stats?.totalReplied || 0,
      icon: MessageSquareReply,
      color: "text-emerald-600",
      bg: "bg-emerald-50 dark:bg-emerald-950",
    },
    {
      label: "Pending Follow-ups",
      value: stats?.pendingFollowUps || 0,
      icon: TrendingUp,
      color: "text-amber-600",
      bg: "bg-amber-50 dark:bg-amber-950",
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Outreach</h1>
          <p className="text-muted-foreground">
            Track cold email campaigns, replies, and lead engagement
          </p>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {statCards.map((card) => (
          <Card key={card.label}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {card.label}
              </CardTitle>
              <div className={`rounded-lg p-2 ${card.bg}`}>
                <card.icon className={`h-4 w-4 ${card.color}`} />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{card.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All Leads</CardTitle>
          <CardDescription>
            {filtered.length} lead{filtered.length !== 1 ? "s" : ""}
            {search ? " matching filter" : ""}
          </CardDescription>
          <div className="relative mt-2">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search by name, email, trade, or city..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-10"
            />
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex h-48 items-center justify-center">
              <p className="text-muted-foreground">Loading leads...</p>
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex h-48 items-center justify-center">
              <p className="text-muted-foreground">
                {search ? "No leads match your search" : "No leads yet. Run the pipeline to start."}
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Business</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Trade</TableHead>
                  <TableHead>Location</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Contacted</TableHead>
                  <TableHead>Last Contact</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((lead) => (
                  <TableRow key={lead.email}>
                    <TableCell className="font-medium">{lead.name}</TableCell>
                    <TableCell className="text-muted-foreground">{lead.email}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="capitalize">
                        {lead.trade || "—"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {lead.city}, {lead.state}
                    </TableCell>
                    <TableCell>
                      <Badge className={STATUS_COLORS[lead.status] || ""}>
                        {lead.status}
                      </Badge>
                    </TableCell>
                    <TableCell>{lead.contactCount}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {lead.lastContacted
                        ? new Date(lead.lastContacted).toLocaleDateString()
                        : "—"}
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setSelectedLead(lead)}
                      >
                        Details
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {selectedLead && (
        <LeadDetailDialog
          lead={selectedLead}
          open={!!selectedLead}
          onOpenChange={(open) => {
            if (!open) setSelectedLead(null);
          }}
        />
      )}
    </div>
  );
}
