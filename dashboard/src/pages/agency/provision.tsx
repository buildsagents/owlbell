import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useProvisionClient } from "@/hooks/use-agency";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Bot,
  Building2,
  CalendarCheck,
  CheckCircle2,
  ClipboardCheck,
  Loader2,
  PhoneForwarded,
  ShieldCheck,
} from "lucide-react";

const INDUSTRIES = [
  "Plumbing", "HVAC", "Electrical", "Roofing", "Pest Control",
  "Automotive", "Beauty & Wellness", "Construction", "Dental", "Education",
  "Financial Services", "Healthcare", "Hospitality", "Insurance", "Legal",
  "Manufacturing", "Medical", "Non-profit", "Real Estate", "Retail",
  "Technology", "Telecommunications", "Transportation", "Other",
];

const PLANS = [
  { value: "starter", label: "Starter ($297/mo)" },
  { value: "professional", label: "Professional ($797/mo)" },
  { value: "pro_plus", label: "Pro Plus ($1,497/mo)" },
  { value: "enterprise", label: "Enterprise ($2,000/mo)" },
];

const TIMEZONES = [
  "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
  "America/Anchorage", "Pacific/Honolulu", "America/Phoenix", "America/Juneau",
  "America/Boise", "America/Indiana/Indianapolis", "America/Detroit",
];

export default function ProvisionClientPage() {
  const navigate = useNavigate();
  const provision = useProvisionClient();
  const [result, setResult] = useState<{ id: string; slug: string } | null>(null);

  const [form, setForm] = useState({
    name: "",
    slug: "",
    email: "",
    phone: "",
    industry: "plumbing",
    plan: "professional",
    timezone: "America/New_York",
    ownerEmail: "",
    ownerName: "",
    primaryGoal: "Book qualified emergency and standard jobs without sounding automated.",
    serviceArea: "",
    escalationContact: "",
    voiceStyle: "Warm, calm, concise receptionist. Natural pauses. No AI disclosure unless asked.",
  });

  const update = (field: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [field]: e.target.value }));

  const handleSubmit = () => {
    provision.mutate(
      {
        name: form.name,
        slug: form.slug || form.name.toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, ""),
        email: form.email,
        phone: form.phone.startsWith("+") ? form.phone : `+1${form.phone.replace(/\D/g, "")}`,
        industry: form.industry,
        plan: form.plan,
        timezone: form.timezone,
        ownerEmail: form.ownerEmail || undefined,
        ownerName: form.ownerName || undefined,
      },
      {
        onSuccess: (data) => {
          setResult(data as { id: string; slug: string });
          toast.success("Client provisioned", {
            description: `${form.name} has been created successfully.`,
          });
        },
        onError: () => {
          toast.error("Provisioning failed", {
            description: "Could not create client. Please try again.",
          });
        },
      }
    );
  };

  if (result) {
    return (
      <div className="space-y-6">
        <PageHeader title="Client Provisioned" description="The new client tenant has been created." />
        <Card>
          <CardContent className="flex flex-col items-center py-12 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-emerald-50">
              <CheckCircle2 className="h-8 w-8 text-emerald-500" />
            </div>
            <h2 className="mt-4 text-xl font-semibold">{form.name}</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Client created successfully with slug: <code className="rounded bg-muted px-1 py-0.5">{result.slug}</code>
            </p>
            <div className="mt-6 grid w-full max-w-2xl gap-3 text-left sm:grid-cols-3">
              {["Tenant ready", "Voice brief queued", "QA call required"].map((item) => (
                <div key={item} className="rounded-lg border bg-background p-3">
                  <CheckCircle2 className="mb-2 h-4 w-4 text-emerald-500" />
                  <p className="text-sm font-medium">{item}</p>
                </div>
              ))}
            </div>
            <div className="mt-6 flex gap-3">
              <Button variant="outline" onClick={() => navigate("/agency/clients")}>
                Back to Clients
              </Button>
              <Button onClick={() => navigate(`/agency/client/${result.id}`)}>
                View Client
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Launch a Client"
        description="Create the tenant and capture the details needed for a polished, human-sounding first build."
      >
        <Button variant="outline" onClick={() => navigate("/agency/clients")}>
          Cancel
        </Button>
      </PageHeader>

      <section className="rounded-lg border bg-slate-950 p-5 text-white shadow-sm">
        <div className="grid gap-4 lg:grid-cols-[1fr_1.1fr] lg:items-center">
          <div>
            <div className="mb-3 inline-flex items-center gap-2 rounded-md bg-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-white/75">
              <ShieldCheck className="h-3.5 w-3.5" />
              Managed setup
            </div>
            <h2 className="text-2xl font-bold tracking-tight">No client should go live from a blank template.</h2>
            <p className="mt-2 text-sm leading-6 text-slate-300">
              Provisioning now starts with the operational brief: what to book, when to escalate, how the receptionist should sound, and what must be QA-tested.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-lg bg-white/10 p-3">
              <Bot className="mb-2 h-5 w-5 text-emerald-300" />
              <p className="text-sm font-semibold">Voice brief</p>
              <p className="mt-1 text-xs text-slate-300">Human tone guardrails</p>
            </div>
            <div className="rounded-lg bg-white/10 p-3">
              <PhoneForwarded className="mb-2 h-5 w-5 text-sky-300" />
              <p className="text-sm font-semibold">Routing</p>
              <p className="mt-1 text-xs text-slate-300">Emergency escalation</p>
            </div>
            <div className="rounded-lg bg-white/10 p-3">
              <CalendarCheck className="mb-2 h-5 w-5 text-amber-300" />
              <p className="text-sm font-semibold">Booking</p>
              <p className="mt-1 text-xs text-slate-300">Qualified job capture</p>
            </div>
          </div>
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[1fr_1fr_0.8fr]">
        <Card>
          <CardHeader>
            <CardTitle>Business Details</CardTitle>
            <CardDescription>Basic account, contact, and service area details.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-sm font-medium mb-1.5">Business Name</p>
              <Input
                placeholder="Acme Corp"
                value={form.name}
                onChange={update("name")}
              />
            </div>
            <div>
              <p className="text-sm font-medium mb-1.5">Slug</p>
              <Input
                placeholder="acme-corp"
                value={form.slug}
                onChange={update("slug")}
              />
            </div>
            <div>
              <p className="text-sm font-medium mb-1.5">Email</p>
              <Input
                type="email"
                placeholder="admin@acme.com"
                value={form.email}
                onChange={update("email")}
              />
            </div>
            <div>
              <p className="text-sm font-medium mb-1.5">Phone</p>
              <Input
                placeholder="+12125551234"
                value={form.phone}
                onChange={update("phone")}
              />
            </div>
            <div>
              <p className="text-sm font-medium mb-1.5">Service Area</p>
              <Input
                placeholder="Austin, Round Rock, Cedar Park"
                value={form.serviceArea}
                onChange={update("serviceArea")}
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Configuration</CardTitle>
            <CardDescription>Commercial package and owner details.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-sm font-medium mb-1.5">Industry</p>
              <Select
                value={form.industry}
                onValueChange={(v) => setForm((prev) => ({ ...prev, industry: v }))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {INDUSTRIES.map((ind) => (
                    <SelectItem key={ind} value={ind.toLowerCase()}>{ind}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <p className="text-sm font-medium mb-1.5">Plan</p>
              <Select
                value={form.plan}
                onValueChange={(v) => setForm((prev) => ({ ...prev, plan: v }))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PLANS.map((p) => (
                    <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <p className="text-sm font-medium mb-1.5">Timezone</p>
              <Select
                value={form.timezone}
                onValueChange={(v) => setForm((prev) => ({ ...prev, timezone: v }))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TIMEZONES.map((tz) => (
                    <SelectItem key={tz} value={tz}>{tz.replace("_", " ")}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <p className="text-sm font-medium mb-1.5">Owner Name (optional)</p>
              <Input
                placeholder="Jane Doe"
                value={form.ownerName}
                onChange={update("ownerName")}
              />
            </div>
            <div>
              <p className="text-sm font-medium mb-1.5">Owner Email (optional)</p>
              <Input
                type="email"
                placeholder="jane@acme.com"
                value={form.ownerEmail}
                onChange={update("ownerEmail")}
              />
            </div>
            <div>
              <p className="text-sm font-medium mb-1.5">Escalation Contact</p>
              <Input
                placeholder="Owner mobile or dispatch line"
                value={form.escalationContact}
                onChange={update("escalationContact")}
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Voice Build Brief</CardTitle>
            <CardDescription>What the setup team should preserve in the agent.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-sm font-medium mb-1.5">Primary Goal</p>
              <textarea
                className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none transition-colors focus:ring-2 focus:ring-ring/20"
                value={form.primaryGoal}
                onChange={(e) => setForm((prev) => ({ ...prev, primaryGoal: e.target.value }))}
              />
            </div>
            <div>
              <p className="text-sm font-medium mb-1.5">Voice Style</p>
              <textarea
                className="min-h-28 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none transition-colors focus:ring-2 focus:ring-ring/20"
                value={form.voiceStyle}
                onChange={(e) => setForm((prev) => ({ ...prev, voiceStyle: e.target.value }))}
              />
            </div>
            <div className="rounded-lg border bg-muted/40 p-3">
              <ClipboardCheck className="mb-2 h-4 w-4 text-primary" />
              <p className="text-sm font-medium">QA checklist starts after provisioning</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Test greeting, interruption handling, emergency triage, booking, SMS handoff, and awkward caller behavior before launch.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="flex justify-end">
        <Button
          size="lg"
          onClick={handleSubmit}
          disabled={!form.name || !form.email || !form.phone || provision.isPending}
        >
          {provision.isPending ? (
            <>
              <Loader2 className="mr-1 h-4 w-4 animate-spin" /> Provisioning...
            </>
          ) : (
            <>
              <Building2 className="mr-1 h-4 w-4" /> Provision Client
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
