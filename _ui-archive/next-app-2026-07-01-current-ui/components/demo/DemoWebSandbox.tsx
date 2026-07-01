"use client";

import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import { CTA_PRIMARY, auditHref } from "@/lib/marketing-cta";

type CallStatus = "idle" | "connecting" | "live" | "ended" | "unavailable" | "error";

type Props = {
  vertical?: string;
  businessName?: string;
};

export default function DemoWebSandbox({ vertical = "plumbing", businessName: _businessName }: Props) {
  void _businessName;
  const clientRef = useRef<{ stopCall: () => void } | null>(null);
  const [status, setStatus] = useState<CallStatus>("idle");
  const [transcript, setTranscript] = useState<string[]>([]);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const endCall = useCallback(() => {
    clientRef.current?.stopCall();
    clientRef.current = null;
    setStatus("ended");
  }, []);

  const startCall = useCallback(async () => {
    setErrorMsg(null);
    setTranscript([]);
    setStatus("connecting");

    try {
      const tokenRes = await fetch("/api/demo/web-call", { method: "POST" });
      if (tokenRes.status === 503) {
        setStatus("unavailable");
        setErrorMsg("Live Retell sandbox is not configured in this environment. Launch onboarding and we will set it up.");
        return;
      }
      if (!tokenRes.ok) throw new Error("Could not create Retell web call");
      const tokenData = await tokenRes.json() as { access_token?: string };
      if (!tokenData.access_token) throw new Error("Retell access token missing");

      const { RetellWebClient } = await import("retell-client-js-sdk");
      const retell = new RetellWebClient();
      clientRef.current = { stopCall: () => retell.stopCall() };

      retell.on("call_started", () => setStatus("live"));
      retell.on("call_ended", () => {
        clientRef.current = null;
        setStatus("ended");
      });
      retell.on("update", (update: { transcript?: string }) => {
        if (update.transcript) {
          setTranscript(update.transcript.split("\n").filter((line) => line.trim()));
        }
      });
      retell.on("error", () => {
        setStatus("error");
        setErrorMsg("Call error. Check microphone permissions and retry.");
      });

      await retell.startCall({ accessToken: tokenData.access_token });
    } catch {
      setStatus("error");
      setErrorMsg("Failed to connect to live sandbox.");
    }
  }, []);

  return (
    <div className="demo-web-sandbox">
      <div className="demo-web-sandbox-status">
        <span className={`demo-web-sandbox-dot demo-web-sandbox-dot--${status}`} aria-hidden />
        {status === "idle" && "Ready - talk to the sample receptionist in your browser"}
        {status === "connecting" && "Connecting. Allow microphone when prompted"}
        {status === "live" && "Live. Speak now; transcript updates below"}
        {status === "ended" && "Call ended. Start another or configure your own agent"}
        {status === "unavailable" && "Live sandbox unavailable in this environment"}
        {status === "error" && (errorMsg || "Something went wrong")}
      </div>

      <div className="hero-dispatch-actions">
        {status === "live" || status === "connecting" ? (
          <button type="button" className="btn btn--secondary" onClick={endCall}>
            End call
          </button>
        ) : (
          <button type="button" className="btn btn--primary" onClick={startCall}>
            Start live web call
          </button>
        )}
        <Link href={auditHref({ source: "demo_sandbox", vertical })} className="btn btn--secondary">
          {CTA_PRIMARY}
        </Link>
      </div>

      {transcript.length > 0 && (
        <div className="demo-web-sandbox-transcript" aria-live="polite">
          {transcript.map((line, i) => (
            <p key={`${i}-${line.slice(0, 24)}`}>{line}</p>
          ))}
        </div>
      )}
    </div>
  );
}
