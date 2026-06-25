import { useState, useEffect } from "react";
import { useNotificationPreferences, useUpdateNotificationPreferences } from "@/hooks/use-notification-settings";
import { PageHeader } from "@/components/layout/PageHeader";
import { LoadingSpinner } from "@/components/shared/loading-spinner";
import { ErrorState } from "@/components/shared/error-state";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "sonner";
import { Save, Bell, Mail, MessageSquare, CalendarDays, Users, AlertTriangle } from "lucide-react";

export default function NotificationSettingsPage() {
  const { data: preferences, isLoading, isError, refetch } = useNotificationPreferences();
  const updatePrefs = useUpdateNotificationPreferences();
  const [settings, setSettings] = useState<Record<string, boolean | string | null>>({});

  useEffect(() => {
    if (preferences) {
      setSettings(preferences as unknown as Record<string, boolean | string | null>);
    }
  }, [preferences]);

  const update = (key: string, value: boolean | string | null) => setSettings((s) => ({ ...s, [key]: value }));

  const handleSave = () => {
    updatePrefs.mutate(settings as Parameters<typeof updatePrefs.mutate>[0], {
      onSuccess: () => toast.success("Notification preferences saved"),
      onError: () => toast.error("Failed to save notification preferences"),
    });
  };

  if (isLoading) return <LoadingSpinner className="py-12" />;
  if (isError) return <ErrorState onRetry={refetch} />;

  return (
    <div className="space-y-6 max-w-2xl">
      <PageHeader title="Notifications" description="Manage your notification preferences">
        <Button onClick={handleSave} disabled={updatePrefs.isPending}>
          <Save className="mr-1 h-4 w-4" /> {updatePrefs.isPending ? "Saving..." : "Save"}
        </Button>
      </PageHeader>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base font-medium">
            <Bell className="h-5 w-5 text-primary" /> Channels
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2"><Mail className="h-4 w-4" /> <span className="text-sm">Email Notifications</span></div>
            <Switch checked={!!settings.emailEnabled} onCheckedChange={(v) => update("emailEnabled", v)} />
          </div>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2"><Bell className="h-4 w-4" /> <span className="text-sm">Push Notifications</span></div>
            <Switch checked={!!settings.pushEnabled} onCheckedChange={(v) => update("pushEnabled", v)} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-medium">Events</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {[
            { key: "callCompleted", label: "Call Completed", icon: Bell },
            { key: "callMissed", label: "Call Missed", icon: AlertTriangle },
            { key: "messageReceived", label: "Message Received", icon: MessageSquare },
            { key: "appointmentBooked", label: "Appointment Booked", icon: CalendarDays },
            { key: "usageWarning", label: "Usage Warning", icon: AlertTriangle },
            { key: "teamInvite", label: "Team Invite", icon: Users },
          ].map((item) => (
            <div key={item.key} className="flex items-center justify-between">
              <div className="flex items-center gap-2"><item.icon className="h-4 w-4 text-muted-foreground" /> <span className="text-sm">{item.label}</span></div>
              <Switch checked={!!settings[item.key]} onCheckedChange={(v) => update(item.key, v)} />
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
