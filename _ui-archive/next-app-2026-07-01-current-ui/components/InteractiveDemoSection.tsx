"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";

/* ── Types ── */
type CallStage = "idle" | "connecting" | "live" | "ended" | "error";
type Speaker = "agent" | "caller" | "thinking";

interface TranscriptLine {
  id: string;
  role: "agent" | "caller";
  text: string;
}

interface DemoActionItem {
  id: string;
  type: "emergency" | "address" | "appointment" | "sms" | "crm";
  label: string;
  description: string;
}

interface SimEvent {
  at: number;
  type: "transcript" | "action" | "speaker" | "end";
  role?: "agent" | "caller";
  text?: string;
  action?: DemoActionItem;
  speaker?: Speaker;
}

/* ── Constants ── */
const WAVE_BARS = 23;

const BAR_HEIGHTS = Array.from({ length: WAVE_BARS }, () => ({
  "--bar-h1": `${4 + Math.random() * 8}px`,
  "--bar-h2": `${12 + Math.random() * 20}px`,
  "--bar-h3": `${6 + Math.random() * 14}px`,
  "--bar-h4": `${16 + Math.random() * 20}px`,
}));

const ACTIONS_ICONS: Record<DemoActionItem["type"], (w: number, h: number) => React.ReactNode> = {
  emergency: (w, h) => (
    <svg width={w} height={h} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 1.5L1.5 13.5h13L8 1.5z" /><path d="M8 6v3" /><circle cx="8" cy="11.5" r="0.5" fill="currentColor" stroke="none" />
    </svg>
  ),
  address: (w, h) => (
    <svg width={w} height={h} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 14s4-4 4-7a4 4 0 00-8 0c0 3 4 7 4 7z" /><circle cx="8" cy="6" r="1.5" />
    </svg>
  ),
  appointment: (w, h) => (
    <svg width={w} height={h} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="2.5" width="12" height="12" rx="1.5" /><path d="M2 6.5h12M5.5 1v3M10.5 1v3" /><path d="M6.5 10.5l1 1 2-2" />
    </svg>
  ),
  sms: (w, h) => (
    <svg width={w} height={h} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 3H2a1 1 0 00-1 1v7a1 1 0 001 1h3l2 2.5L9 12h3a1 1 0 001-1V4a1 1 0 00-1-1z" />
    </svg>
  ),
  crm: (w, h) => (
    <svg width={w} height={h} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M11 2.5H5a2 2 0 00-2 2V12l2-1.5h6a2 2 0 002-2v-4a2 2 0 00-2-2z" /><circle cx="8" cy="6" r="1" /><path d="M6.5 9.5a2.5 2.5 0 013 0" />
    </svg>
  ),
};

const SIMULATION_EVENTS: SimEvent[] = [
  { at: 0.0, type: "speaker", speaker: "agent" },
  { at: 0.15, type: "transcript", role: "agent", text: "Thanks for calling Northstar Plumbing, this is Morgan. Are you calling about an emergency, or would you like to book a visit?" },
  { at: 0.8, type: "speaker", speaker: "caller" },
  { at: 1.0, type: "transcript", role: "caller", text: "It's an emergency. A pipe has burst under the sink and water is still coming through." },
  { at: 1.5, type: "speaker", speaker: "thinking" },
  { at: 1.7, type: "action", action: { id: "emergency-1", type: "emergency", label: "Emergency detected", description: "Burst pipe - active flooding - after hours" } },
  { at: 1.9, type: "speaker", speaker: "agent" },
  { at: 2.05, type: "transcript", role: "agent", text: "I can help with that. If you can do it safely, turn off the stopcock. What name and address should I give the on-call plumber?" },
  { at: 2.6, type: "speaker", speaker: "caller" },
  { at: 2.8, type: "transcript", role: "caller", text: "Sarah Mitchell, 24 Maple Road, Bristol, BS6 5AL. We turned it off but there is still water on the floor." },
  { at: 3.3, type: "speaker", speaker: "thinking" },
  { at: 3.5, type: "action", action: { id: "address-1", type: "address", label: "Address captured", description: "24 Maple Road, Bristol, BS6 5AL" } },
  { at: 3.7, type: "speaker", speaker: "agent" },
  { at: 3.85, type: "transcript", role: "agent", text: "Thanks, Sarah. I have the address and I am marking this as active flooding. Is this the best number for the plumber to call back on?" },
  { at: 4.8, type: "speaker", speaker: "caller" },
  { at: 5.0, type: "transcript", role: "caller", text: "Yes, this number is fine. We're home all night if someone can come or call." },
  { at: 5.5, type: "speaker", speaker: "thinking" },
  { at: 5.7, type: "action", action: { id: "appt-1", type: "appointment", label: "Emergency slot held", description: "On-call escalation - 8:30 AM follow-up" } },
  { at: 5.9, type: "speaker", speaker: "agent" },
  { at: 6.05, type: "transcript", role: "agent", text: "I am alerting the on-call plumber now and holding an 8:30 AM follow-up if the emergency visit needs repair work. You will get a text confirmation in a moment." },
  { at: 6.8, type: "speaker", speaker: "thinking" },
  { at: 7.0, type: "action", action: { id: "sms-1", type: "sms", label: "Owner SMS sent", description: "Emergency - burst pipe - Sarah M. - active water" } },
  { at: 7.15, type: "action", action: { id: "crm-1", type: "crm", label: "CRM entry created", description: "Emergency job - Sarah M. - Bristol" } },
  { at: 7.35, type: "speaker", speaker: "agent" },
  { at: 7.5, type: "transcript", role: "agent", text: "While you wait, keep clear of standing water near sockets. If the water reaches electrics, leave that area and tell the plumber when they call." },
  { at: 8.1, type: "speaker", speaker: "caller" },
  { at: 8.3, type: "transcript", role: "caller", text: "Okay, thank you. That's much better than leaving a voicemail." },
  { at: 8.8, type: "speaker", speaker: "agent" },
  { at: 8.95, type: "transcript", role: "agent", text: "You're welcome. The on-call team has the details, and this number is on the job. Stay safe, Sarah." },
  { at: 9.6, type: "speaker", speaker: "thinking" },
  { at: 10.0, type: "end" },
];

/* ── Sub-components ── */

function Waveform({ speaker }: { speaker: Speaker }) {
  return (
    <div className={`demo-call-waveform demo-call-waveform--${speaker}`}>
      {BAR_HEIGHTS.map((vars, i) => (
        <div
          key={i}
          className="demo-call-wavebar"
          style={{
            ...vars,
            animationDelay: `${(i * 0.07).toFixed(3)}s`,
            animationDuration: speaker === "thinking" ? "0.4s" : speaker === "caller" ? "0.3s" : "0.4s",
          }}
        />
      ))}
    </div>
  );
}

function SpeakerLabel({ speaker }: { speaker: Speaker }) {
  const label = speaker === "agent" ? "Receptionist speaking"
    : speaker === "caller" ? "Caller speaking"
    : speaker === "thinking" ? "Processing details..."
    : "";
  return (
    <div className={`demo-call-speaker demo-call-speaker--${speaker}`} aria-live="polite">
      {label}
    </div>
  );
}

function TranscriptLines({ lines }: { lines: TranscriptLine[] }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);
  return (
    <div className="demo-call-transcript-wrap" role="log" aria-label="Call transcript" aria-live="polite">
      {lines.length === 0 && (
        <div className="demo-call-placeholder">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
            <path d="M6 7h8M6 10h5" />
          </svg>
          Conversation will appear here
        </div>
      )}
      {lines.map((line) => (
        <div key={line.id} className={`demo-call-line demo-call-line--${line.role}`}>
          <span className={`demo-call-line-badge demo-call-line-badge--${line.role}`} aria-hidden />
          <span className="demo-call-line-text">{line.text}</span>
        </div>
      ))}
      <div ref={endRef} />
    </div>
  );
}

function ActionsFeed({ items }: { items: DemoActionItem[] }) {
  if (items.length === 0) return null;
  return (
    <div className="demo-call-actions" aria-label="Live actions">
      {items.map((a) => (
        <div key={a.id} className="demo-call-action">
          <span className={`demo-call-action-icon demo-call-action-icon--${a.type}`} aria-hidden>
            {ACTIONS_ICONS[a.type](14, 14)}
          </span>
          <div className="demo-call-action-body">
            <div className="demo-call-action-label">{a.label}</div>
            <div className="demo-call-action-desc">{a.description}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

/* ── Main component ── */

export default function InteractiveDemoSection() {
  const [stage, setStage] = useState<CallStage>("idle");
  const [speaker, setSpeaker] = useState<Speaker>("thinking");
  const [lines, setLines] = useState<TranscriptLine[]>([]);
  const [actions, setActions] = useState<DemoActionItem[]>([]);
  const [timer, setTimer] = useState(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const clientRef = useRef<{ stopCall: () => void } | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const simRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  const clearTimers = useCallback(() => {
    simRef.current.forEach(clearTimeout);
    simRef.current = [];
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
  }, []);

  const resetAll = useCallback(() => {
    clearTimers();
    setTimer(0);
    setLines([]);
    setActions([]);
    setSpeaker("thinking");
    setErrorMsg(null);
  }, [clearTimers]);

  const startSimulated = useCallback(() => {
    resetAll();
    setStage("connecting");
    setSpeaker("thinking");

    // Brief connecting delay, then go live
    const connectTimer = setTimeout(() => {
      setStage("live");
      setSpeaker("agent");

      // Start timer
      const startTime = Date.now();
      timerRef.current = setInterval(() => {
        setTimer(Math.floor((Date.now() - startTime) / 1000));
      }, 200);

      // Schedule events
      const events = SIMULATION_EVENTS;
      const scheduled: ReturnType<typeof setTimeout>[] = [];

      events.forEach((ev) => {
        scheduled.push(setTimeout(() => {
          if (ev.type === "transcript" && ev.role && ev.text) {
            setLines((prev) => [...prev, { id: `l-${prev.length}-${Date.now()}`, role: ev.role!, text: ev.text! }]);
            setSpeaker(ev.role);
          } else if (ev.type === "action" && ev.action) {
            setActions((prev) => [...prev, ev.action!]);
          } else if (ev.type === "speaker" && ev.speaker) {
            setSpeaker(ev.speaker);
          } else if (ev.type === "end") {
            setSpeaker("thinking");
            setTimeout(() => {
              setStage("ended");
              if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
            }, 400);
          }
        }, ev.at * 1000));
      });

      simRef.current = scheduled;
    }, 300);

    simRef.current = [connectTimer];
  }, [resetAll]);

  const startLive = useCallback(async () => {
    resetAll();
    setStage("connecting");

    try {
      const tokenRes = await fetch("/api/demo/web-call", { method: "POST" });
      if (!tokenRes.ok) {
        startSimulated();
        return;
      }
      const tokenData = await tokenRes.json() as { access_token?: string };
      if (!tokenData.access_token) {
        startSimulated();
        return;
      }

      const { RetellWebClient } = await import("retell-client-js-sdk");
      const retell = new RetellWebClient();
      clientRef.current = { stopCall: () => retell.stopCall() };

      const startTime = Date.now();

      retell.on("call_started", () => {
        setStage("live");
        setSpeaker("agent");
        timerRef.current = setInterval(() => {
          setTimer(Math.floor((Date.now() - startTime) / 1000));
        }, 200);
      });

      retell.on("call_ended", () => {
        clientRef.current = null;
        setStage("ended");
        if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
        setSpeaker("thinking");
      });

      retell.on("agent_start_talking", () => setSpeaker("agent"));
      retell.on("agent_stop_talking", () => setSpeaker("thinking"));
      retell.on("update", (update: { transcript?: string }) => {
        if (update.transcript) {
          const transcriptText = update.transcript;
          const nextLines = transcriptText
            .split("\n")
            .filter((line) => line.trim())
            .map((line, index) => {
              const isAgent = /^(Agent|agent|Assistant|assistant):/.test(line);
              const text = line.replace(/^(Agent|User|Assistant|agent|user|assistant):\s*/, "");
              return {
                id: `retell-${index}-${text.slice(0, 12)}`,
                role: isAgent ? "agent" as const : "caller" as const,
                text,
              };
            });
          setLines(nextLines);
          const last = nextLines[nextLines.length - 1];
          if (last) setSpeaker(last.role);
          const lower = transcriptText.toLowerCase();
          if (lower.includes("emergency") || lower.includes("burst") || lower.includes("flood")) {
            setActions((prev) => prev.some((a) => a.id === "live-emergency") ? prev : [...prev, {
              id: "live-emergency", type: "emergency", label: "Emergency detected", description: "Keyword match from conversation",
            }]);
          }
          if (lower.includes("address") || /\d{1,5}\s+\w+/.test(transcriptText)) {
            setActions((prev) => prev.some((a) => a.id === "live-address") ? prev : [...prev, {
              id: "live-address", type: "address", label: "Address captured", description: transcriptText.slice(0, 40),
            }]);
          }
          if (lower.includes("morning") || lower.includes("tomorrow") || lower.includes("appointment")) {
            setActions((prev) => prev.some((a) => a.id === "live-appt") ? prev : [...prev, {
              id: "live-appt", type: "appointment", label: "Appointment discussed", description: "Time mentioned by caller",
            }]);
          }
        }
      });

      retell.on("error", () => {
        setErrorMsg("Call error. Check microphone permissions.");
        setStage("error");
      });

      await retell.startCall({ accessToken: tokenData.access_token });
    } catch {
      startSimulated();
    }
  }, [resetAll, startSimulated]);

  const endCall = useCallback(() => {
    clientRef.current?.stopCall();
    clientRef.current = null;
    clearTimers();
    setStage("ended");
    setSpeaker("thinking");
  }, [clearTimers]);

  const startCall = useCallback(() => {
    startLive();
  }, [startLive]);

  const duration = useMemo(() => {
    const m = Math.floor(timer / 60);
    const s = timer % 60;
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }, [timer]);

  return (
    <section className="section section--alt" id="interactive-demo">
      <div className="wrap">
        <div className="section-lead">
          <span className="section-label">Demo flow</span>
          <h2>Talk to the Retell receptionist before a client goes live.</h2>
          <p>Start a live browser call. If Retell is unavailable in this environment, the scripted flow still shows the intake logic.</p>
        </div>

        <div className="demo-call-card">
          <div className="demo-call-display">
            {/* ── Top bar ── */}
            <div className="demo-call-topbar">
              <div className="demo-call-topbar-left">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="2" y="1" width="10" height="12" rx="2" /><path d="M5 5h4M5 8h4" />
                </svg>
                Receptionist demo
              </div>
              <span className={`demo-call-status-dot demo-call-status-dot--${stage}`} aria-hidden />
              {stage === "live" && <span className="demo-call-timer">{duration}</span>}
            </div>

            {/* ── Waveform ── */}
            {(stage === "live" || stage === "ended") && (
              <>
                <Waveform speaker={stage === "ended" ? "thinking" : speaker} />
                <SpeakerLabel speaker={stage === "ended" ? "thinking" : speaker} />
              </>
            )}

            {/* ── Transcript ── */}
            {(stage === "live" || stage === "ended") && <TranscriptLines lines={lines} />}

            {/* ── Actions ── */}
            {(stage === "live" || stage === "ended") && <ActionsFeed items={actions} />}

            {/* ── Summary after ended ── */}
            {(stage === "ended" && actions.length > 0) && (
              <div className="demo-call-summary">
                <div className="demo-call-summary-row">
                  <div className="demo-call-stat">
                    <div className="demo-call-stat-value">{duration}</div>
                    <div className="demo-call-stat-label">Call duration</div>
                  </div>
                  <div className="demo-call-stat">
                    <div className="demo-call-stat-value">{lines.length}</div>
                    <div className="demo-call-stat-label">Messages</div>
                  </div>
                  <div className="demo-call-stat">
                    <div className="demo-call-stat-value">{actions.length}</div>
                    <div className="demo-call-stat-label">Actions taken</div>
                  </div>
                </div>
              </div>
            )}

            {/* ── Error ── */}
            {stage === "error" && (
              <div className="demo-call-error">
                <p>{errorMsg || "Something went wrong with the live demo."}</p>
                <button type="button" className="btn btn--ghost" onClick={startCall}>Try again</button>
              </div>
            )}

            {/* ── Overlay: idle / connecting ── */}
            {(stage === "idle" || stage === "connecting") && (
              <div className={`demo-call-overlay${stage === "connecting" ? " demo-call-overlay--connecting" : ""}`}>
                {stage === "idle" && (
                  <>
                    <div className="demo-call-overlay-icon">
                      <svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M17 9.5a5.5 5.5 0 10-11 0c0 4 5.5 8.5 5.5 8.5s5.5-4.5 5.5-8.5z" /><circle cx="11" cy="9.5" r="2" />
                      </svg>
                    </div>
                    <div className="demo-call-overlay-title">Press start to run<br />the emergency intake</div>
                    <div className="demo-call-overlay-desc">Connects to the Retell live sandbox when keys are configured.</div>
                  </>
                )}
                {stage === "connecting" && (
                  <>
                    <div className="demo-call-overlay-icon">
                      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                        <circle cx="10" cy="10" r="7" /><path d="M10 4v2M10 14v2M4 10h2M14 10h2" />
                      </svg>
                    </div>
                    <div className="demo-call-overlay-title">Connecting...</div>
                    <div className="demo-call-overlay-desc">Allow microphone access when prompted by your browser.</div>
                  </>
                )}
              </div>
            )}
          </div>

          {/* ── Controls ── */}
          {stage === "idle" && (
            <div className="demo-call-controls">
              <button type="button" className="demo-call-start-btn" onClick={startCall}>
                <svg width="18" height="18" viewBox="0 0 18 18" fill="currentColor">
                  <path d="M5 2.5l10 6.5-10 6.5V2.5z" />
                </svg>
                Start Demo Call
              </button>
            </div>
          )}
          {stage === "connecting" && (
            <div className="demo-call-controls">
              <button type="button" className="demo-call-start-btn" disabled>
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="9" cy="9" r="7" strokeDasharray="30 20" />
                </svg>
                Connecting...
              </button>
            </div>
          )}
          {stage === "live" && (
            <div className="demo-call-controls">
              <button type="button" className="demo-call-end-btn" onClick={endCall} aria-label="End call">
                <svg viewBox="0 0 20 20" fill="currentColor">
                  <path d="M4.5 12.5c1.5 1.5 3.5 2.5 5.5 2.5s4-.9 5.5-2.5l2 2C15.5 17 12.8 18 10 18s-5.5-1-7.5-3.5l2-2z" />
                  <path d="M10 1c2.5 0 5 .8 7 2.5l-2 2C13.5 4.5 11.8 4 10 4S6.5 4.5 5 5.5l-2-2C5 1.8 7.5 1 10 1z" />
                </svg>
              </button>
            </div>
          )}
          {stage === "ended" && (
            <div className="demo-call-controls">
              <button type="button" className="demo-call-start-btn" onClick={startCall}>
                <svg width="18" height="18" viewBox="0 0 18 18" fill="currentColor">
                  <path d="M5 2.5l10 6.5-10 6.5V2.5z" />
                </svg>
                Try Again
              </button>
              <Link href="/onboarding?source=demo_retry" className="btn btn--secondary btn--lg">
                Book a Demo
              </Link>
            </div>
          )}
          {stage === "error" && (
            <div className="demo-call-controls">
              <button type="button" className="demo-call-start-btn" onClick={startCall}>
                Try Again
              </button>
              <Link href="/demo" className="btn btn--secondary btn--lg">
                Open Demo Page
              </Link>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
