import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { API_ENDPOINTS } from "@/lib/constants";
import {
  DEMO_AGENCY_CLIENTS,
  DEMO_AGENCY_OVERVIEW,
  DEMO_ONBOARDING_PIPELINE,
  getDemoAgencyClient,
  shouldUseDemoData,
} from "@/lib/demo-data";

interface AgencyOverview {
  totalClients: number;
  activeClients: number;
  trialClients: number;
  totalCallsThisMonth: number;
  totalCallsLastMonth: number;
  mrr: number;
  arr: number;
  avgCallsPerClient: number;
  topIndustries: { industry: string; count: number }[];
  onboardingPipeline: Record<string, number>;
}

interface ClientSummary {
  id: string;
  slug: string;
  name: string;
  plan: string;
  status: string;
  industry: string | null;
  phone: string | null;
  createdAt: string | null;
  callsThisMonth: number;
  callsLastMonth: number;
  revenueMtd: number;
  onboardingStep: number;
  onboardingComplete: boolean;
}

interface OnboardingStep {
  step: number;
  name: string;
  description: string;
  completed: boolean;
  completedAt: string | null;
}

interface ClientDetail {
  id: string;
  slug: string;
  name: string;
  plan: string;
  status: string;
  industry: string | null;
  phone: string | null;
  email: string | null;
  timezone: string | null;
  createdAt: string | null;
  greeting: string | null;
  onboarding: OnboardingStep[];
  callsThisMonth: number;
  avgAnswerTime: number | null;
  bookingRate: number | null;
  revenueMtd: number;
}

interface CreateClientRequest {
  name: string;
  slug: string;
  phone: string;
  email: string;
  industry: string;
  plan: string;
  timezone: string;
  ownerEmail?: string;
  ownerName?: string;
}

interface OnboardingPipeline {
  steps: { step: number; name: string; description: string }[];
  clients: {
    clientId: string;
    name: string;
    slug: string;
    currentStep: number;
    totalSteps: number;
    complete: boolean;
    currentStepName: string;
  }[];
}

interface AgencyFilters {
  status?: string;
  industry?: string;
  search?: string;
}

const AGENCY = API_ENDPOINTS.agency;

export function useAgencyOverview() {
  return useQuery<AgencyOverview>({
    queryKey: ["agency", "overview"],
    queryFn: async () => {
      try {
        const response = await api.get<AgencyOverview>(AGENCY.overview);
        return response.data;
      } catch {
        if (shouldUseDemoData()) return DEMO_AGENCY_OVERVIEW;
        throw new Error("Agency overview unavailable");
      }
    },
    staleTime: 60000,
  });
}

export function useAgencyClients(filters?: AgencyFilters) {
  return useQuery<ClientSummary[]>({
    queryKey: ["agency", "clients", filters],
    queryFn: async () => {
      try {
        const params = new URLSearchParams();
        if (filters?.status) params.set("status", filters.status);
        if (filters?.industry) params.set("industry", filters.industry);
        if (filters?.search) params.set("search", filters.search);
        const qs = params.toString();
        const response = await api.get<ClientSummary[]>(`${AGENCY.clients}${qs ? `?${qs}` : ""}`);
        return response.data;
      } catch {
        if (!shouldUseDemoData()) throw new Error("Agency clients unavailable");
        let clients = DEMO_AGENCY_CLIENTS;
        if (filters?.status) clients = clients.filter((client) => client.status === filters.status);
        if (filters?.industry) clients = clients.filter((client) => client.industry === filters.industry);
        if (filters?.search) {
          const q = filters.search.toLowerCase();
          clients = clients.filter(
            (client) =>
              client.name.toLowerCase().includes(q) ||
              client.slug.toLowerCase().includes(q) ||
              (client.industry ?? "").toLowerCase().includes(q),
          );
        }
        return clients;
      }
    },
    staleTime: 30000,
  });
}

export function useAgencyClient(id: string) {
  return useQuery<ClientDetail>({
    queryKey: ["agency", "client", id],
    queryFn: async () => {
      try {
        const response = await api.get<ClientDetail>(AGENCY.client(id));
        return response.data;
      } catch {
        if (shouldUseDemoData()) return getDemoAgencyClient(id);
        throw new Error("Agency client unavailable");
      }
    },
    enabled: !!id,
    staleTime: 30000,
  });
}

export function useProvisionClient() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: CreateClientRequest) => {
      const response = await api.post(AGENCY.clients, data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agency", "clients"] });
      queryClient.invalidateQueries({ queryKey: ["agency", "overview"] });
    },
  });
}

export function useUpdateClient() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...data }: { id: string } & Record<string, unknown>) => {
      const response = await api.put(AGENCY.client(id), data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agency", "clients"] });
      queryClient.invalidateQueries({ queryKey: ["agency", "client"] });
    },
  });
}

export function useAdvanceOnboarding() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (clientId: string) => {
      const response = await api.post(AGENCY.advanceOnboarding(clientId));
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agency", "client"] });
      queryClient.invalidateQueries({ queryKey: ["agency", "overview"] });
      queryClient.invalidateQueries({ queryKey: ["agency", "onboarding"] });
    },
  });
}

export function useOnboardingPipeline() {
  return useQuery<OnboardingPipeline>({
    queryKey: ["agency", "onboarding"],
    queryFn: async () => {
      try {
        const response = await api.get<OnboardingPipeline>(AGENCY.onboardingPipeline);
        return response.data;
      } catch {
        if (shouldUseDemoData()) return DEMO_ONBOARDING_PIPELINE;
        throw new Error("Onboarding pipeline unavailable");
      }
    },
    staleTime: 30000,
  });
}
