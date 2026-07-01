import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { cn } from "@/lib/utils";
import type { VoicePersona, VoiceGender, AiModel } from "@/types/settings";
import { User, UserCircle, Sparkles, Zap, CircleDot } from "lucide-react";

const PERSONAS: { id: VoicePersona; label: string; description: string; icon: React.ComponentType<{className?: string}> }[] = [
  { id: "professional", label: "Professional", description: "Formal and business-oriented", icon: User },
  { id: "friendly", label: "Friendly", description: "Warm and approachable", icon: UserCircle },
  { id: "warm", label: "Warm", description: "Caring and empathetic", icon: Sparkles },
  { id: "energetic", label: "Energetic", description: "Enthusiastic and upbeat", icon: Zap },
  { id: "calm", label: "Calm", description: "Relaxed and soothing", icon: CircleDot },
];

const GENDERS: { id: VoiceGender; label: string }[] = [
  { id: "female", label: "Female" },
  { id: "male", label: "Male" },
  { id: "neutral", label: "Neutral" },
];

const MODELS: { id: AiModel; label: string; description: string }[] = [
  { id: "llama3.1:8b", label: "Llama 3.1 (8B)", description: "Fast, good for most use cases" },
  { id: "llama3.1:70b", label: "Llama 3.1 (70B)", description: "More capable, slower responses" },
  { id: "mixtral:8x7b", label: "Mixtral (8x7B)", description: "Best reasoning, highest quality" },
];

interface AIVoiceSettingsProps {
  settings: {
    voicePersona: VoicePersona;
    voiceGender: VoiceGender;
    voiceSpeed: number;
    aiModel: AiModel;
    transferEnabled: boolean;
    voicemailEnabled: boolean;
    appointmentBookingEnabled: boolean;
    messageTakingEnabled: boolean;
  };
  onChange: (settings: Partial<AIVoiceSettingsProps["settings"]>) => void;
}

export function AIVoiceSettings({ settings, onChange }: AIVoiceSettingsProps) {
  return (
    <div className="space-y-6">
      {/* Voice Persona */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-medium">Voice Persona</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {PERSONAS.map((p) => {
              const Icon = p.icon;
              return (
                <button
                  key={p.id}
                  onClick={() => onChange({ voicePersona: p.id })}
                  className={cn(
                    "flex flex-col items-center gap-2 rounded-lg border p-4 text-center transition-all hover:bg-accent",
                    settings.voicePersona === p.id
                      ? "border-primary bg-primary/5"
                      : "border-border"
                  )}
                >
                  <Icon className="h-6 w-6 text-primary" />
                  <div>
                    <p className="text-sm font-medium">{p.label}</p>
                    <p className="text-xs text-muted-foreground">{p.description}</p>
                  </div>
                </button>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Voice Gender */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-medium">Voice Gender</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            {GENDERS.map((g) => (
              <button
                key={g.id}
                onClick={() => onChange({ voiceGender: g.id })}
                className={cn(
                  "rounded-lg border px-4 py-2 text-sm font-medium transition-all",
                  settings.voiceGender === g.id
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border hover:bg-accent"
                )}
              >
                {g.label}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Voice Speed */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-medium">Voice Speed</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <span className="text-sm text-muted-foreground">Slow</span>
            <Slider
              value={[settings.voiceSpeed]}
              onValueChange={([v]) => onChange({ voiceSpeed: v })}
              min={0.5}
              max={2}
              step={0.1}
              className="flex-1"
            />
            <span className="text-sm text-muted-foreground">Fast</span>
            <span className="ml-2 min-w-12 rounded-md bg-muted px-2 py-1 text-center text-sm font-medium tabular-nums">
              {settings.voiceSpeed.toFixed(1)}x
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Response model */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-medium">Response Model</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {MODELS.map((m) => (
              <button
                key={m.id}
                onClick={() => onChange({ aiModel: m.id })}
                className={cn(
                  "flex w-full items-center gap-3 rounded-lg border p-3 text-left transition-all",
                  settings.aiModel === m.id
                    ? "border-primary bg-primary/5"
                    : "border-border hover:bg-accent"
                )}
              >
                <div
                  className={cn(
                    "h-4 w-4 rounded-full border-2",
                    settings.aiModel === m.id
                      ? "border-primary bg-primary"
                      : "border-muted-foreground"
                  )}
                />
                <div>
                  <p className="text-sm font-medium">{m.label}</p>
                  <p className="text-xs text-muted-foreground">{m.description}</p>
                </div>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Feature Toggles */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-medium">Features</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {[
            { key: "transferEnabled" as const, label: "Call Transfer", desc: "Allow transferring to human agents" },
            { key: "voicemailEnabled" as const, label: "Voicemail", desc: "Record voicemails when unavailable" },
            { key: "appointmentBookingEnabled" as const, label: "Appointment Booking", desc: "Receptionist can schedule appointments" },
            { key: "messageTakingEnabled" as const, label: "Message Taking", desc: "Receptionist takes messages from callers" },
          ].map((feature) => (
            <div key={feature.key} className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">{feature.label}</p>
                <p className="text-xs text-muted-foreground">{feature.desc}</p>
              </div>
              <Switch
                checked={settings[feature.key]}
                onCheckedChange={(checked) => onChange({ [feature.key]: checked })}
              />
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
