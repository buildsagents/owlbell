"use client";

import { useEffect, useState } from "react";
import { CallRecord, MOCK_CALLS } from "@/lib/dashboard-types";

function CallDetail({ call, onClose }: { call: CallRecord; onClose: () => void }) {
  return (
    <div className="dash-detail-overlay" onClick={onClose}>
      <div className="dash-detail-panel" onClick={(e) => e.stopPropagation()}>
        <div className="dash-detail-header">
          <h3>Call details</h3>
          <button type="button" className="dash-detail-close" onClick={onClose}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M4 4l8 8M12 4l-8 8" /></svg>
          </button>
        </div>
        <div className="dash-detail-body">
          <div className="dash-detail-row"><span>Caller</span><span>{call.callerName}</span></div>
          <div className="dash-detail-row"><span>Number</span><span>{call.callerNumber}</span></div>
          <div className="dash-detail-row"><span>Duration</span><span>{call.duration ? `${Math.floor(call.duration / 60)}:${String(call.duration % 60).padStart(2, "0")}` : "-"}</span></div>
          <div className="dash-detail-row"><span>Status</span><span className={`dash-badge dash-badge--${call.status}`}>{call.status}</span></div>
          <div className="dash-detail-row"><span>Time</span><span>{new Date(call.timestamp).toLocaleString()}</span></div>
          <div className="dash-detail-row dash-detail-row--full"><span>Summary</span><span>{call.summary}</span></div>
        </div>
      </div>
    </div>
  );
}

export default function DashboardCalls() {
  const [calls] = useState<CallRecord[]>(MOCK_CALLS);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [selectedCall, setSelectedCall] = useState<CallRecord | null>(null);

  const filtered = calls.filter((c) => {
    if (statusFilter !== "all" && c.status !== statusFilter) return false;
    if (search && !c.callerName.toLowerCase().includes(search.toLowerCase()) && !c.callerNumber.includes(search)) return false;
    return true;
  });

  return (
    <div className="dash-page">
      <h1 className="dash-page-title">Call History</h1>
      <p className="dash-page-subtitle">{calls.length} total calls</p>

      <div className="dash-toolbar">
        <input className="dash-search" type="text" placeholder="Search by name or number..." value={search} onChange={(e) => setSearch(e.target.value)} />
        <div className="dash-filter-group">
          {["all", "completed", "missed", "failed"].map((f) => (
            <button key={f} type="button" className={`dash-filter-btn${statusFilter === f ? ' dash-filter-btn--active' : ''}`} onClick={() => setStatusFilter(f)}>
              {f === "all" ? "All" : f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <div className="dash-call-list">
        {filtered.map((call) => (
          <button key={call.id} type="button" className="dash-call-row dash-call-row--clickable" onClick={() => setSelectedCall(call)}>
            <div className="dash-call-info">
              <div className="dash-call-name">{call.callerName}</div>
              <div className="dash-call-number">{call.callerNumber}</div>
            </div>
            <div className="dash-call-summary">{call.summary}</div>
            <div className="dash-call-meta">
              <span className={`dash-badge dash-badge--${call.status}`}>{call.status}</span>
              <span className="dash-call-duration">{call.duration ? `${Math.floor(call.duration / 60)}:${String(call.duration % 60).padStart(2, "0")}` : "-"}</span>
            </div>
          </button>
        ))}
        {filtered.length === 0 && <p className="dash-empty">No calls match your filters.</p>}
      </div>

      {selectedCall && <CallDetail call={selectedCall} onClose={() => setSelectedCall(null)} />}
    </div>
  );
}
