'use client';

import { useState, useEffect } from 'react';
import { createClient } from '@/lib/supabase/client';
import { Agent } from '@/types';

const API_V1 = `${(process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/+$/, '')}/api/v1`;

export default function SettingsPage() {
  const [agent, setAgent] = useState<Agent | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [form, setForm] = useState({
    greeting: '',
    system_prompt: '',
    voice_id: '',
    phone_number: '',
  });

  useEffect(() => {
    const supabase = createClient();

    async function load() {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session?.access_token) throw new Error('Not authenticated');

        const res = await fetch(`${API_V1}/client-portal/agent`, {
          headers: { Authorization: `Bearer ${session.access_token}` },
        });

        if (res.ok) {
          const data = (await res.json()) as Agent | { agent: Agent };
          const agentData = 'agent' in data ? data.agent : data;
          setAgent(agentData);
          setForm({
            greeting: agentData.greeting ?? '',
            system_prompt: agentData.system_prompt ?? '',
            voice_id: agentData.voice_id ?? '',
            phone_number: agentData.phone_number ?? '',
          });
        } else {
          console.error('Failed to fetch agent:', res.status);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load agent configuration');
      } finally {
        setLoading(false);
      }
    }

    load();
  }, []);

  const handleSave = async () => {
    if (!agent) return;
    setSaving(true);

    try {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.access_token) throw new Error('Not authenticated');

      const res = await fetch(`${API_V1}/client-portal/agent`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({
          greeting: form.greeting,
          system_prompt: form.system_prompt,
          voice_id: form.voice_id,
        }),
      });

      if (res.ok) {
        await fetch('/api/voice/update-agent', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ agentId: agent.id, ...form }),
        });
        setSaved(true);
        setTimeout(() => setSaved(false), 3000);
      } else {
        console.error('Failed to save agent:', res.status);
      }
    } catch (err) {
      console.error('Save failed:', err);
    } finally {
      setSaving(false);
    }
  };

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '11px 14px',
    borderRadius: '10px',
    border: '1px solid var(--line)',
    background: 'var(--panel2)',
    color: 'var(--ink)',
    fontSize: '14px',
    fontFamily: 'inherit',
    outline: 'none',
  };

  const labelStyle: React.CSSProperties = {
    display: 'block',
    fontSize: '13px',
    fontWeight: 600,
    color: 'var(--muted)',
    marginBottom: '6px',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  };

  if (error) {
    return (
      <div style={{
        color: '#f87171', padding: '40px', textAlign: 'center',
        background: 'var(--panel)', borderRadius: '16px',
        border: '1px solid rgba(239,68,68,0.3)',
      }}>
        <div style={{ fontSize: '18px', fontWeight: 700, marginBottom: '8px' }}>Failed to load settings</div>
        <div style={{ fontSize: '14px', opacity: 0.8 }}>{error}</div>
      </div>
    );
  }

  if (loading) {
    return <div style={{ color: 'var(--muted)', padding: '40px' }}>Loading agent configuration…</div>;
  }

  return (
    <div>
      <div style={{ marginBottom: '28px' }}>
        <h1 style={{ margin: 0, fontSize: '26px', fontWeight: 800, letterSpacing: '-0.02em' }}>
          Agent Settings
        </h1>
        <p style={{ margin: '4px 0 0', color: 'var(--muted)', fontSize: '14px' }}>
          Configure how your AI receptionist sounds and behaves.
        </p>
      </div>

      <div style={{
        display: 'grid', gap: '20px',
        maxWidth: '780px',
      }}>
        {/* Phone number */}
        <div style={{
          background: 'var(--panel)', border: '1px solid var(--line)',
          borderRadius: '16px', padding: '24px',
        }}>
          <h2 style={{ margin: '0 0 18px', fontSize: '17px', fontWeight: 700 }}>Phone Number</h2>
          <label style={labelStyle}>Your Owlbell number</label>
          <input
            style={{ ...inputStyle, color: 'var(--muted)' }}
            value={form.phone_number || 'Not yet provisioned'}
            disabled
            readOnly
          />
          <p style={{ margin: '8px 0 0', fontSize: '13px', color: 'var(--muted)' }}>
            Forward your existing number to this one when busy or after hours.
            Carrier code: <code style={{ color: 'var(--accent)' }}>*72{form.phone_number}</code> on most carriers.
          </p>
        </div>

        {/* Greeting */}
        <div style={{
          background: 'var(--panel)', border: '1px solid var(--line)',
          borderRadius: '16px', padding: '24px',
        }}>
          <h2 style={{ margin: '0 0 18px', fontSize: '17px', fontWeight: 700 }}>Greeting</h2>
          <label style={labelStyle}>Opening line (first thing callers hear)</label>
          <input
            style={inputStyle}
            value={form.greeting}
            onChange={e => setForm({ ...form, greeting: e.target.value })}
            placeholder="Thanks for calling Rapid Plumbing, how can I help you today?"
          />
          <p style={{ margin: '8px 0 0', fontSize: '13px', color: 'var(--muted)' }}>
            Include your business name so callers know they've reached the right place.
          </p>
        </div>

        {/* System prompt */}
        <div style={{
          background: 'var(--panel)', border: '1px solid var(--line)',
          borderRadius: '16px', padding: '24px',
        }}>
          <h2 style={{ margin: '0 0 4px', fontSize: '17px', fontWeight: 700 }}>Knowledge Base</h2>
          <p style={{ margin: '0 0 16px', fontSize: '13px', color: 'var(--muted)' }}>
            Tell the AI about your business: hours, services, service areas, pricing, FAQs, and emergency procedures.
          </p>
          <label style={labelStyle}>Business instructions for your AI</label>
          <textarea
            style={{ ...inputStyle, minHeight: '220px', resize: 'vertical', lineHeight: 1.6 }}
            value={form.system_prompt}
            onChange={e => setForm({ ...form, system_prompt: e.target.value })}
            placeholder={`Business name: Rapid Plumbing Services
Owner: Mike Johnson
Phone for emergencies: (512) 555-0101

Hours: Mon–Fri 8am–6pm, Sat 9am–2pm, 24/7 emergency line

Services: Drain cleaning, water heater repair/install, leak detection, pipe repair, slab leaks

Service area: Austin TX and surrounding areas within 30 miles

FAQs:
- Emergency callout fee: $150 after hours
- Water heater install: $800–$1,200 depending on unit
- Free estimates for all non-emergency work

Emergency protocol: If caller says water is actively flooding or there's no hot water in winter, escalate immediately to Mike's cell.`}
          />
        </div>

        {/* Voice selection */}
        <div style={{
          background: 'var(--panel)', border: '1px solid var(--line)',
          borderRadius: '16px', padding: '24px',
        }}>
          <h2 style={{ margin: '0 0 18px', fontSize: '17px', fontWeight: 700 }}>Voice</h2>
          <label style={labelStyle}>Voice ID (ElevenLabs / Cartesia)</label>
          <input
            style={inputStyle}
            value={form.voice_id}
            onChange={e => setForm({ ...form, voice_id: e.target.value })}
            placeholder="e.g. 11labs-Adrian or a Cartesia voice UUID"
          />
          <p style={{ margin: '8px 0 0', fontSize: '13px', color: 'var(--muted)' }}>
            Contact support to preview and change your AI's voice.
          </p>
        </div>

        {/* Save */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <button
            className="btn btn-primary"
            onClick={handleSave}
            disabled={saving}
            style={{ opacity: saving ? 0.6 : 1, cursor: saving ? 'wait' : 'pointer' }}
          >
            {saving ? 'Saving…' : 'Save changes'}
          </button>
          {saved && (
            <span style={{ color: 'var(--good)', fontSize: '14px', fontWeight: 600 }}>
              ✓ Changes saved and pushed to your AI agent
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
