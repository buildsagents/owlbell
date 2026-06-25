'use client';

import { useState, useEffect } from 'react';
import { createClient } from '@/lib/supabase/client';
import { Call, Subscription } from '@/types';

const API_V1 = `${(process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/+$/, '')}/api/v1`;

function StatCard({ label, value, sub, color = 'var(--brand2)' }: {
  label: string; value: string | number; sub?: string; color?: string;
}) {
  return (
    <div style={{
      background: 'var(--panel)',
      border: '1px solid var(--line)',
      borderRadius: '16px',
      padding: '22px 24px',
    }}>
      <div style={{ fontSize: '13px', color: 'var(--muted)', marginBottom: '6px' }}>{label}</div>
      <div style={{ fontSize: '36px', fontWeight: 800, color, letterSpacing: '-0.02em', lineHeight: 1.1 }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: '13px', color: 'var(--muted)', marginTop: '4px' }}>{sub}</div>}
    </div>
  );
}

function CallRow({ call }: { call: Call }) {
  const isEmergency = call.action_items?.is_emergency;
  const hasBooking = call.action_items?.appointment_booked;
  const date = new Date(call.created_at).toLocaleString('en-US', {
    month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
  });
  const dur = call.duration_seconds
    ? `${Math.floor(call.duration_seconds / 60)}m ${call.duration_seconds % 60}s`
    : '—';

  return (
    <tr style={{ borderBottom: '1px solid var(--line)' }}>
      <td style={{ padding: '12px 14px', fontSize: '14px', color: 'var(--muted)' }}>{date}</td>
      <td style={{ padding: '12px 14px', fontSize: '14px' }}>{call.caller_number || 'Unknown'}</td>
      <td style={{ padding: '12px 14px' }}>
        {isEmergency && (
          <span style={{
            display: 'inline-block', fontSize: '11px', fontWeight: 700,
            background: 'rgba(239,68,68,0.12)', color: '#f87171',
            border: '1px solid rgba(239,68,68,0.3)', borderRadius: '999px',
            padding: '2px 9px', marginRight: '6px',
          }}>🚨 Emergency</span>
        )}
        {hasBooking && (
          <span style={{
            display: 'inline-block', fontSize: '11px', fontWeight: 700,
            background: 'rgba(52,211,153,0.12)', color: 'var(--good)',
            border: '1px solid rgba(52,211,153,0.3)', borderRadius: '999px',
            padding: '2px 9px',
          }}>✓ Booked</span>
        )}
        {!isEmergency && !hasBooking && (
          <span style={{ fontSize: '13px', color: 'var(--muted)' }}>Message taken</span>
        )}
      </td>
      <td style={{ padding: '12px 14px', fontSize: '13px', color: 'var(--muted)' }}>{dur}</td>
      <td style={{ padding: '12px 14px', fontSize: '13px', color: 'var(--muted)', maxWidth: '280px' }}>
        <span style={{
          overflow: 'hidden', display: '-webkit-box',
          WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
        }}>
          {call.summary || '—'}
        </span>
      </td>
    </tr>
  );
}

export default function DashboardPage() {
  const [calls, setCalls] = useState<Call[]>([]);
  const [sub, setSub] = useState<Subscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const supabase = createClient();

    async function load() {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session?.access_token) throw new Error('Not authenticated');

        const headers = { Authorization: `Bearer ${session.access_token}` };

        const [callsRes, overviewRes] = await Promise.all([
          fetch(`${API_V1}/client-portal/calls`, { headers }),
          fetch(`${API_V1}/client-portal/overview`, { headers }),
        ]);

        if (callsRes.ok) {
          const data = await callsRes.json();
          setCalls(Array.isArray(data) ? data : (data as { calls: Call[] }).calls ?? []);
        } else {
          console.error('Failed to fetch calls:', callsRes.status);
        }

        if (overviewRes.ok) {
          const data = await overviewRes.json() as { subscription?: Subscription };
          if (data.subscription) setSub(data.subscription);
        } else {
          console.error('Failed to fetch overview:', overviewRes.status);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load dashboard data');
      } finally {
        setLoading(false);
      }
    }

    load();
  }, []);

  const totalCalls = calls.length;
  const bookedCalls = calls.filter(c => c.action_items?.appointment_booked).length;
  const emergencies = calls.filter(c => c.action_items?.is_emergency).length;
  const avgDuration = calls.length
    ? Math.round(calls.reduce((s, c) => s + (c.duration_seconds ?? 0), 0) / calls.length)
    : 0;

  if (error) {
    return (
      <div style={{
        color: '#f87171', padding: '40px', textAlign: 'center',
        background: 'var(--panel)', borderRadius: '16px',
        border: '1px solid rgba(239,68,68,0.3)',
      }}>
        <div style={{ fontSize: '18px', fontWeight: 700, marginBottom: '8px' }}>Failed to load dashboard</div>
        <div style={{ fontSize: '14px', opacity: 0.8 }}>{error}</div>
      </div>
    );
  }

  return (
    <div>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ margin: 0, fontSize: '26px', fontWeight: 800, letterSpacing: '-0.02em' }}>
          Overview
        </h1>
        <p style={{ margin: '4px 0 0', color: 'var(--muted)', fontSize: '14px' }}>
          Your AI receptionist activity — last 50 calls
        </p>
      </div>

      {/* Stat cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '28px' }}>
        <StatCard label="Total Calls" value={loading ? '…' : totalCalls} sub="this period" />
        <StatCard label="Jobs Booked" value={loading ? '…' : bookedCalls} sub="via AI" color="var(--good)" />
        <StatCard label="Emergencies Routed" value={loading ? '…' : emergencies} sub="escalated to you" color="#f87171" />
        <StatCard
          label="Avg Call Duration"
          value={loading ? '…' : avgDuration ? `${Math.floor(avgDuration / 60)}m ${avgDuration % 60}s` : '—'}
          sub="per call"
          color="var(--accent)"
        />
      </div>

      {/* Plan status banner */}
      {sub && (
        <div style={{
          background: 'linear-gradient(135deg, rgba(245,158,11,0.10), rgba(56,189,248,0.07))',
          border: '1px solid rgba(245,158,11,0.3)',
          borderRadius: '12px',
          padding: '14px 20px',
          marginBottom: '24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '16px',
        }}>
          <div>
            <span style={{ fontWeight: 700, color: 'var(--brand2)', textTransform: 'capitalize' }}>
              {sub.plan_tier} Plan
            </span>
            <span style={{ fontSize: '13px', color: 'var(--muted)', marginLeft: '10px' }}>
              Status: {sub.status}
              {sub.current_period_end &&
                ` · renews ${new Date(sub.current_period_end).toLocaleDateString()}`}
            </span>
          </div>
          <a
            href="/dashboard/billing"
            style={{
              fontSize: '13px', fontWeight: 700, color: 'var(--brand2)',
              textDecoration: 'none', padding: '6px 14px',
              border: '1px solid rgba(245,158,11,0.4)', borderRadius: '8px',
            }}
          >
            Manage billing →
          </a>
        </div>
      )}

      {/* Calls table */}
      <div style={{
        background: 'var(--panel)',
        border: '1px solid var(--line)',
        borderRadius: '16px',
        overflow: 'hidden',
      }}>
        <div style={{ padding: '18px 20px', borderBottom: '1px solid var(--line)' }}>
          <h2 style={{ margin: 0, fontSize: '17px', fontWeight: 700 }}>Recent Calls</h2>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Time', 'Caller', 'Outcome', 'Duration', 'Summary'].map(h => (
                  <th key={h} style={{
                    padding: '10px 14px', textAlign: 'left', fontSize: '12px',
                    fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase',
                    letterSpacing: '0.05em', borderBottom: '1px solid var(--line)',
                    background: 'var(--panel2)',
                  }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} style={{ padding: '32px', textAlign: 'center', color: 'var(--muted)' }}>
                    Loading calls…
                  </td>
                </tr>
              ) : calls.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ padding: '32px', textAlign: 'center', color: 'var(--muted)' }}>
                    No calls yet. Your AI receptionist is live and ready.
                  </td>
                </tr>
              ) : (
                calls.map(call => <CallRow key={call.id} call={call} />)
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
