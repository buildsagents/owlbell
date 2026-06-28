const METRICS = [
  {
    id: "revenue",
    label: "Revenue Recovered",
    value: "$14,850",
    change: "18.6%",
    icon: (
      <svg viewBox="0 0 48 24" fill="none" aria-hidden>
        <path
          d="M2 18 10 12 18 14 28 6 38 10 46 4"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
  {
    id: "calls",
    label: "Calls Answered",
    value: "247",
    change: "12.4%",
    icon: (
      <svg viewBox="0 0 48 24" fill="none" aria-hidden>
        <path
          d="M2 20 12 10 20 14 30 8 40 12 46 6"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
  {
    id: "jobs",
    label: "Jobs Booked",
    value: "38",
    change: "26.7%",
    icon: (
      <svg viewBox="0 0 48 24" fill="none" aria-hidden>
        <path
          d="M2 16 14 10 22 12 32 4 42 8 46 2"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
  {
    id: "missed",
    label: "Missed Calls Prevented",
    value: "52",
    change: "8.3%",
    icon: (
      <svg viewBox="0 0 48 24" fill="none" aria-hidden>
        <path
          d="M2 14 10 8 18 12 26 6 34 10 42 4 46 6"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
];

const TRANSCRIPT = [
  { time: "10:24:13", speaker: "Owlbell Reception", text: "Thank you for calling Summit Plumbing Co. This is Alex with the Owlbell reception team. How can I help you today?" },
  { time: "10:24:18", speaker: "Caller", text: "Hi, yeah—I've got a burst pipe in my basement and water is everywhere. I need someone out ASAP." },
  { time: "10:24:21", speaker: "Owlbell Reception", text: "I'm so sorry to hear that. I can get a tech to you right away. Are you available this morning, or would afternoon work better?" },
  { time: "10:24:27", speaker: "Caller", text: "This morning if possible." },
  { time: "10:24:29", speaker: "Owlbell Reception", text: "Great. I have a 11:00 AM slot open with our lead tech, Jake. Does that work?" },
  { time: "10:24:33", speaker: "Caller", text: "Yeah, that's perfect." },
  { time: "10:24:35", speaker: "Owlbell Reception", text: "Excellent. You're all set for 11:00 AM. The tech will call when they're on the way. Is this the best number to reach you?" },
  { time: "10:24:39", speaker: "Caller", text: "Yes." },
  { time: "10:24:40", speaker: "Owlbell Reception", text: "Thank you. If anything changes, we'll let you know. Have a good morning." },
];

const NOTIFICATIONS = [
  {
    time: "10:24 AM",
    body: "Job summary: Burst pipe repair for Michael Thompson. Scheduled for 11:00 AM today, $850 estimated.",
  },
  {
    time: "9:47 AM",
    body: "Job summary: Water heater diagnostic for Sarah Johnson. Scheduled for 1:30 PM today, $275 estimated.",
  },
  {
    time: "8:59 AM",
    body: "Job summary: Kitchen sink clog for David Lee. Scheduled for 3:00 PM today, $325 estimated.",
  },
];

const NAV_TABS = ["Dashboard", "Calls", "Bookings", "Analytics", "Settings"];

export default function DashboardMockup() {
  return (
    <section className="section" id="dashboard">
      <div className="wrap">
        <header className="section-header">
          <span className="section-eyebrow">Agency command center</span>
          <h2>Full Visibility Into Every Call Your Agency Handles</h2>
          <p>
            Your dedicated dashboard shows recovered revenue, live calls in
            progress, and instant owner alerts — the same view our success team
            uses to tune performance.
          </p>
        </header>

        <div
          className="dash-mock dash-mock--static"
          aria-label="Illustrative Owlbell dashboard preview — not interactive"
        >
          <span className="dash-mock-badge">Illustrative preview</span>
          <div className="dash-mock-chrome">
            {/* Top nav */}
            <header className="dash-nav">
              <div className="dash-nav-brand">
                <svg className="dash-nav-logo" viewBox="0 0 32 32" fill="none" aria-hidden>
                  <circle cx="16" cy="16" r="15" fill="#f59e0b" />
                  <ellipse cx="11" cy="14" rx="4.5" ry="5" fill="#fff" />
                  <ellipse cx="21" cy="14" rx="4.5" ry="5" fill="#fff" />
                  <circle cx="11" cy="14" r="2.2" fill="#0f172a" />
                  <circle cx="21" cy="14" r="2.2" fill="#0f172a" />
                  <path d="M16 19.5c-2.2 0-4 1.2-4.8 3 1.6 1.2 3.2 1.8 4.8 1.8s3.2-.6 4.8-1.8c-.8-1.8-2.6-3-4.8-3z" fill="#fff" />
                </svg>
                <span className="dash-nav-name">Owlbell</span>
              </div>

              <nav className="dash-nav-tabs" aria-label="Dashboard navigation">
                {NAV_TABS.map((tab) => (
                  <span
                    key={tab}
                    className={`dash-nav-tab${tab === "Dashboard" ? " dash-nav-tab--active" : ""}`}
                  >
                    {tab}
                  </span>
                ))}
              </nav>

              <div className="dash-nav-user">
                <button type="button" className="dash-company-btn" tabIndex={-1}>
                  Summit Plumbing Co.
                  <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden>
                    <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 0 1 1.06.02L10 11.168l3.71-3.94a.75.75 0 1 1 1.08 1.04l-4.25 4.5a.75.75 0 0 1-1.08 0l-4.25-4.5a.75.75 0 0 1 .02-1.06Z" clipRule="evenodd" />
                  </svg>
                </button>
                <div className="dash-avatar" aria-hidden>
                  <span>JT</span>
                </div>
              </div>
            </header>

            {/* Metrics */}
            <div className="dash-metrics">
              {METRICS.map((m) => (
                <div key={m.id} className="dash-metric">
                  <div className="dash-metric-top">
                    <span className="dash-metric-label">{m.label}</span>
                    <span className="dash-metric-spark">{m.icon}</span>
                  </div>
                  <div className="dash-metric-value">{m.value}</div>
                  <div className="dash-metric-change">
                    <span className="dash-metric-arrow" aria-hidden>↑</span>
                    {m.change} vs last 7 days
                  </div>
                </div>
              ))}
            </div>

            {/* Main panels */}
            <div className="dash-panels">
              <div className="dash-panel dash-panel--call">
                <div className="dash-panel-head">
                  <div className="dash-live-label">
                    <span className="dash-live-dot" aria-hidden />
                    Live Call
                  </div>
                  <span className="dash-badge dash-badge--live">In Progress</span>
                </div>

                <div className="dash-caller">
                  <div className="dash-caller-avatar" aria-hidden>
                    <svg viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm0 2c-4.42 0-8 2.24-8 5v1h16v-1c0-2.76-3.58-5-8-5Z" />
                    </svg>
                  </div>
                  <div>
                    <div className="dash-caller-name">Michael Thompson</div>
                    <div className="dash-caller-phone">(303) 555-0187</div>
                  </div>
                </div>

                <div className="dash-transcript">
                  {TRANSCRIPT.map((line) => (
                    <div key={line.time} className="dash-transcript-line">
                      <span className="dash-transcript-time">{line.time}</span>
                      <span className={`dash-transcript-speaker${line.speaker === "Caller" ? " dash-transcript-speaker--caller" : ""}`}>
                        {line.speaker}:
                      </span>
                      <span className="dash-transcript-text">{line.text}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="dash-panel dash-panel--notifications">
                <h3 className="dash-panel-title">Recent Text Notifications</h3>
                <ul className="dash-notifications">
                  {NOTIFICATIONS.map((n) => (
                    <li key={n.time} className="dash-notification">
                      <time className="dash-notification-time">{n.time}</time>
                      <p className="dash-notification-meta">
                        Text message sent to owner (720) 555-0148
                      </p>
                      <p className="dash-notification-body">{n.body}</p>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}