"use client";

import { useCallback, useState } from "react";
import { AgentConfig, MOCK_AGENT_CONFIG } from "@/lib/dashboard-types";

const VOICES = [
  { id: '79a125e8-cd45-4c13-8a67-188112f4dd22', name: 'Morgan', style: 'Professional - clear, warm, confident' },
  { id: 'f982d1e4-e8b0-4a9e-b8db-2d8c7a4321ab', name: 'Alex', style: 'Friendly - approachable, conversational' },
  { id: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890', name: 'Sam', style: 'Neutral - calm, measured, reassuring' },
];

export default function DashboardSettings() {
  const [config, setConfig] = useState<AgentConfig>(MOCK_AGENT_CONFIG);
  const [saved, setSaved] = useState(false);

  const update = <K extends keyof AgentConfig>(key: K, value: AgentConfig[K]) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
  };

  const handleSave = useCallback(() => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }, []);

  return (
    <div className="dash-page">
      <h1 className="dash-page-title">Agent Settings</h1>
      <p className="dash-page-subtitle">Configure your AI receptionist</p>

      <div className="dash-settings">
        <div className="dash-settings-section">
          <h3>Greeting</h3>
          <p className="dash-settings-hint">What callers hear when the AI answers</p>
          <textarea className="dash-input dash-input--textarea" value={config.greeting} onChange={(e) => update("greeting", e.target.value)} rows={3} />
        </div>

        <div className="dash-settings-section">
          <h3>System prompt</h3>
          <p className="dash-settings-hint">Instructions that guide the AI behaviour</p>
          <textarea className="dash-input dash-input--textarea" value={config.systemPrompt} onChange={(e) => update("systemPrompt", e.target.value)} rows={6} />
        </div>

        <div className="dash-settings-section">
          <h3>Voice</h3>
          <p className="dash-settings-hint">Select the voice your receptionist uses</p>
          <div className="dash-voice-grid">
            {VOICES.map((voice) => (
              <button
                key={voice.id}
                type="button"
                className={`dash-voice-card${config.voiceId === voice.id ? " dash-voice-card--active" : ""}`}
                onClick={() => { update("voiceId", voice.id); update("voiceName", voice.name); }}
              >
                <div className="dash-voice-name">{voice.name}</div>
                <div className="dash-voice-style">{voice.style}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="dash-settings-section">
          <h3>Business hours</h3>
          <p className="dash-settings-hint">When the AI uses standard vs emergency routing</p>
          <input className="dash-input" type="text" value={config.businessHours} onChange={(e) => update("businessHours", e.target.value)} />
        </div>

        <div className="dash-settings-section">
          <h3>Emergency routing</h3>
          <p className="dash-settings-hint">How emergency calls are handled outside business hours</p>
          <select className="dash-input" value={config.emergencyRouting} onChange={(e) => update("emergencyRouting", e.target.value)}>
            <option value="Escalate to on-call team">Escalate to on-call team</option>
            <option value="Book next available slot">Book next available slot</option>
            <option value="Business hours only">Business hours only</option>
          </select>
        </div>

        <div className="dash-settings-actions">
          <button type="button" className="btn btn--primary" onClick={handleSave}>
            {saved ? "Saved ✓" : "Save changes"}
          </button>
        </div>
      </div>
    </div>
  );
}
