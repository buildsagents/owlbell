import { useState, useEffect } from "react";
import { useAISettings, useUpdateAISettings } from "@/hooks/use-settings";
import { AIVoiceSettings } from "@/components/settings/AIVoiceSettings";
import { PageHeader } from "@/components/layout/PageHeader";
import { LoadingSpinner } from "@/components/shared/loading-spinner";
import { ErrorState } from "@/components/shared/error-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScriptEditor } from "@/components/editors/ScriptEditor";
import { Slider } from "@/components/ui/slider";
import { toast } from "sonner";
import { Bot, Save } from "lucide-react";

export default function AiPersonalityPage() {
  const { data: settings, isLoading, isError, refetch } = useAISettings();
  const updateSettings = useUpdateAISettings();
  const [localSettings, setLocalSettings] = useState<Partial<NonNullable<typeof settings>>>({});

  useEffect(() => {
    if (settings) {
      setLocalSettings(settings);
    }
  }, [settings]);

  const handleSave = () => {
    updateSettings.mutate(localSettings, {
      onSuccess: () => toast.success("Receptionist settings saved successfully"),
      onError: () => toast.error("Failed to save receptionist settings"),
    });
  };

  if (isLoading) return <LoadingSpinner className="py-12" />;
  if (isError) return <ErrorState onRetry={refetch} />;
  if (!settings) return null;

  const voiceSettings = {
    voicePersona: localSettings.voicePersona || settings.voicePersona,
    voiceGender: localSettings.voiceGender || settings.voiceGender,
    voiceSpeed: localSettings.voiceSpeed ?? settings.voiceSpeed,
    aiModel: localSettings.aiModel || settings.aiModel,
    transferEnabled: localSettings.transferEnabled ?? settings.transferEnabled,
    voicemailEnabled: localSettings.voicemailEnabled ?? settings.voicemailEnabled,
    appointmentBookingEnabled: localSettings.appointmentBookingEnabled ?? settings.appointmentBookingEnabled,
    messageTakingEnabled: localSettings.messageTakingEnabled ?? settings.messageTakingEnabled,
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <PageHeader title="Voice Setup" description="Configure how your receptionist sounds and responds">
        <Button onClick={handleSave} disabled={updateSettings.isPending}>
          <Save className="mr-1 h-4 w-4" /> {updateSettings.isPending ? "Saving..." : "Save Changes"}
        </Button>
      </PageHeader>

      {/* Greeting & Farewell */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base font-medium">
            <Bot className="h-5 w-5 text-primary" />
            Greeting & Farewell
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <ScriptEditor
            storageKey="ai-greeting"
            label="Greeting message"
            placeholder="Hello, thank you for calling..."
            maxLength={500}
            rows={4}
            value={localSettings.greeting || settings.greeting || ""}
            onChange={(greeting) => setLocalSettings((s) => ({ ...s, greeting }))}
          />
          <ScriptEditor
            storageKey="ai-farewell"
            label="Farewell message"
            placeholder="Thank you for calling, have a great day!"
            maxLength={500}
            rows={3}
            value={localSettings.farewell || settings.farewell || ""}
            onChange={(farewell) => setLocalSettings((s) => ({ ...s, farewell }))}
          />
        </CardContent>
      </Card>

      {/* Max Call Duration */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-medium">Max Call Duration</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <Slider
              value={[(localSettings.maxCallDuration || settings.maxCallDuration || 600) / 60]}
              onValueChange={([v]) => setLocalSettings((s) => ({ ...s, maxCallDuration: v * 60 }))}
              min={1}
              max={60}
              step={1}
              className="flex-1"
            />
            <span className="min-w-20 rounded-md bg-muted px-2 py-1 text-center text-sm font-medium tabular-nums">
              {(localSettings.maxCallDuration || settings.maxCallDuration || 600) / 60} min
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Voice and response settings */}
      <AIVoiceSettings
        settings={voiceSettings}
        onChange={(updates) => setLocalSettings((s) => ({ ...s, ...updates }))}
      />
    </div>
  );
}
