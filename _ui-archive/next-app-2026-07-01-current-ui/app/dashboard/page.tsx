"use client";

import { useEffect, useState } from "react";
import { AlertItem, CallRecord, DashboardStats, MOCK_ALERTS, MOCK_CALLS, MOCK_STATS } from "@/lib/dashboard-types";

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="dash-stat-card">
      <div className="dash-stat-value">{value}</div>
      <div className="dash-stat-label">{label}</div>
      {sub && <div className="dash-stat-sub">{sub}</div>}
    </div>
  );
}

function CallRow({ call }: { call: CallRecord }) {
  const statusClass = `dash-badge dash-badge--${call.status}`;
  const statusLabel = call.status === 'completed' ? 'Completed' : call.status === 'missed' ? 'Missed' : call.status === 'failed' ? 'Failed' : 'In progress';
  return (
    <div className="dash-call-row">
      <div className="dash-call-info">
        <div className="dash-call-name">{call.callerName}</div>
        <div className="dash-call-number">{call.callerNumber}</div>
      </div>
      <div className="dash-call-summary">{call.summary}</div>
      <div className="dash-call-meta">
        <span className={statusClass}>{statusLabel}</span>
        <span className="dash-call-duration">{call.duration ? `${Math.floor(call.duration / 60)}:${String(call.duration % 60).padStart(2, "0")}` : "-"}</span>
      </div>
    </div>
  );
}

function AlertRow({ alert }: { alert: AlertItem }) {
  return (
    <div className={`dash-alert-row${alert.read ? '' : ' dash-alert-row--unread'}`}>
      <div className={`dash-alert-dot dash-alert-dot--${alert.type}`} />
      <div className="dash-alert-body">
        <div className="dash-alert-message">{alert.message}</div>
        <div className="dash-alert-time">{new Date(alert.timestamp).toLocaleString()}</div>
      </div>
    </div>
  );
}

export default function DashboardOverview() {
  const [stats] = useState<DashboardStats>(MOCK_STATS);
  const [calls] = useState<CallRecord[]>(MOCK_CALLS.slice(0, 5));
  const [alerts] = useState<AlertItem[]>(MOCK_ALERTS);

  return (
    <div className="dash-page">
      <h1 className="dash-page-title">Overview</h1>
      <p className="dash-page-subtitle">Active since {stats.activeSince}</p>

      <div className="dash-stats-grid">
        <StatCard label="Total calls" value={String(stats.totalCalls)} sub={`${stats.answeredCalls} answered`} />
        <StatCard label="Answered" value={String(stats.answeredCalls)} sub={`${((stats.answeredCalls / stats.totalCalls) * 100).toFixed(1)}% rate`} />
        <StatCard label="Appointments" value={String(stats.appointmentsBooked)} sub="booked via AI" />
        <StatCard label="Avg response" value={`${stats.avgResponseTime}s`} sub="first response time" />
      </div>

      <div className="dash-section">
        <h2 className="dash-section-title">Recent calls</h2>
        <div className="dash-call-list">
          {calls.map((call) => <CallRow key={call.id} call={call} />)}
        </div>
      </div>

      <div className="dash-section">
        <h2 className="dash-section-title">Alerts</h2>
        <div className="dash-alert-list">
          {alerts.map((alert) => <AlertRow key={alert.id} alert={alert} />)}
        </div>
      </div>
    </div>
  );
}
