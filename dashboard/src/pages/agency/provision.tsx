import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useProvisionClient } from "@/hooks/use-agency";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Building2, CheckCircle2 } from "lucide-react";

const INDUSTRIES = [
  "Automotive", "Beauty & Wellness", "Construction", "Dental", "Education",
  "Financial Services", "Healthcare", "Hospitality", "Insurance", "Legal",
  "Manufacturing", "Medical", "Non-profit", "Real Estate", "Retail",
  "Technology", "Telecommunications", "Transportation", "other",
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
    industry: "other",
    plan: "starter",
    timezone: "America/New_York",
    ownerEmail: "",
    ownerName: "",
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
        onSuccess: (data) => setResult(data as { id: string; slug: string }),
        onError: () => {},
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
      <PageHeader title="Provision Client" description="Create a new client tenant">
        <Button variant="outline" onClick={() => navigate("/agency/clients")}>
          Cancel
        </Button>
      </PageHeader>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Business Details</CardTitle>
            <CardDescription>Enter the client's business information.</CardDescription>
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
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Configuration</CardTitle>
            <CardDescription>Set the plan, industry, and timezone.</CardDescription>
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
          </CardContent>
        </Card>
      </div>

      <div className="flex justify-end">
        <Button
          size="lg"
          onClick={handleSubmit}
          disabled={!form.name || !form.email || !form.phone || provision.isPending}
        >
          {provision.isPending ? "Provisioning..." : (
            <>
              <Building2 className="mr-1 h-4 w-4" /> Provision Client
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
