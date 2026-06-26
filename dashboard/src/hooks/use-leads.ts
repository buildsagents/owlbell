import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/lib/api";

interface Reply {
  body: string;
  classification: string;
  timestamp: string;
}

interface Outcome {
  type: string;
  stage?: number;
  note?: string;
  timestamp: string;
}

export interface Lead {
  name: string;
  email: string;
  phone: string;
  website: string;
  trade: string;
  city: string;
  state: string;
  firstContacted: string;
  lastContacted: string | null;
  contactCount: number;
  followUpStage: number;
  status: string;
  outcomes: Outcome[];
  replies: Reply[];
  lastNote?: string;
}

export interface LeadStats {
  total: number;
  sent: number;
  replied: number;
  bounced: number;
  pendingFollowUps: number;
  totalSent: number;
  totalReplied: number;
  totalBounced: number;
}

const CRON_SECRET = import.meta.env.VITE_LEADS_CRON_SECRET || "owlbell-leads-cron-2026";

function leadsUrl(path: string) {
  return `/leads${path}?secret=${CRON_SECRET}`;
}

export function useLeads() {
  return useQuery<Lead[]>({
    queryKey: ["leads"],
    queryFn: () => apiRequest<Lead[]>("get", leadsUrl("/all")),
    refetchInterval: 60_000,
  });
}

export function useLeadStats() {
  return useQuery<LeadStats>({
    queryKey: ["leads", "stats"],
    queryFn: () => apiRequest<LeadStats>("get", leadsUrl("/stats")),
    refetchInterval: 60_000,
  });
}
