"use client";

import { useEffect } from "react";

const DASHBOARD_URL =
  (process.env.NEXT_PUBLIC_DASHBOARD_URL || "https://app.owlbell.xyz").replace(/\/+$/, "");

export default function DashboardCallsRedirect() {
  useEffect(() => {
    window.location.replace(`${DASHBOARD_URL}/dashboard/calls`);
  }, []);

  return (
    <main style={{ padding: "2rem", fontFamily: "system-ui, sans-serif" }}>
      <p>Redirecting to call history…</p>
    </main>
  );
}