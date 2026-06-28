const COMPARISON_ROWS = [
  {
    option: "Missed calls / voicemail",
    cost: "$0",
    calls: "None",
    jobs: "0",
    highlight: false,
  },
  {
    option: "Hiring a receptionist",
    cost: "$4,000 – $6,000+",
    calls: "Business hours",
    jobs: "2 – 6 (avg)",
    highlight: false,
  },
  {
    option: "Owlbell Launch",
    cost: "$1,497",
    calls: "Unlimited",
    jobs: "Lead capture + alerts",
    highlight: false,
  },
  {
    option: "Owlbell Growth",
    cost: "$4,997",
    calls: "Unlimited 24/7",
    jobs: "Booking + recovery workflow",
    highlight: true,
  },
  {
    option: "Owlbell Scale",
    cost: "$9,997+",
    calls: "Multi-location",
    jobs: "Enterprise routing + SLAs",
    highlight: false,
  },
];

const SUPPORT_CARDS = [
  {
    id: "setup",
    title: "White-Glove Agency Setup",
    description:
      "A dedicated onboarding specialist builds your scripts, wires your calendar, and configures routing — you never touch a dashboard on day one.",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
        <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0ZM12 14a7 7 0 0 0-7 7h14a7 7 0 0 0-7-7Z" />
      </svg>
    ),
  },
  {
    id: "support",
    title: "Dedicated Success Team",
    description:
      "US-based humans who know your account, tune scripts monthly, and answer the phone when you need us — not a ticket queue.",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
        <path strokeLinecap="round" strokeLinejoin="round" d="M4 14v2a2 2 0 0 0 2 2h1l2 3h6l2-3h1a2 2 0 0 0 2-2v-2M7 10a5 5 0 0 1 10 0v1H7v-1Z" />
      </svg>
    ),
  },
];

function ShieldIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path
        fillRule="evenodd"
        d="M12 2.25c-2.34 0-4.5.52-6.2 1.44-.9.5-1.8 1.16-1.8 2.06v6.5c0 3.78 2.55 7.18 6.2 8.54 3.65-1.36 6.2-4.76 6.2-8.54v-6.5c0-.9-.9-1.56-1.8-2.06-1.7-.92-3.86-1.44-6.2-1.44Zm4.28 6.53-4.5 4.5a.75.75 0 0 1-1.06 0l-2-2a.75.75 0 1 1 1.06-1.06l1.47 1.47 3.97-3.97a.75.75 0 1 1 1.06 1.06Z"
        clipRule="evenodd"
      />
    </svg>
  );
}

export default function HonestMathSection() {
  return (
    <section className="section section--alt" id="honest-math">
      <div className="wrap">
        <header className="section-header section-header--wide">
          <span className="section-eyebrow">The honest math</span>
          <h2>Premium Agency Pricing — When the Numbers Work</h2>
          <p>
            At $1,497–$9,997/mo, Owlbell only makes sense when missed calls are
            already costing you real revenue. We build around your call volume,
            average job value, and crew capacity.
          </p>
          <p className="section-header-sub">
            Subscribe online in minutes — white-glove onboarding starts within 24 hours.
          </p>
        </header>

        <div className="honest-main agency-card agency-card--flush">
          <div className="honest-guarantee">
            <div className="honest-guarantee-icon">
              <ShieldIcon />
            </div>
            <p className="honest-guarantee-text">
              5 jobs booked in your first 30 days — or we keep working until you get there
            </p>
          </div>

          <div className="honest-table-wrap">
            <table className="honest-table">
              <thead>
                <tr>
                  <th scope="col">Option</th>
                  <th scope="col">Monthly Cost</th>
                  <th scope="col">Calls Covered</th>
                  <th scope="col">Jobs Booked</th>
                </tr>
              </thead>
              <tbody>
                {COMPARISON_ROWS.map((row) => (
                  <tr
                    key={row.option}
                    className={row.highlight ? "honest-table-row--highlight" : undefined}
                  >
                    <td className="honest-table-option" data-label="Option">
                      {row.option}
                    </td>
                    <td data-label="Monthly Cost">{row.cost}</td>
                    <td data-label="Calls Covered">{row.calls}</td>
                    <td data-label="Jobs Booked">
                      {row.jobs}
                      {row.highlight && (
                        <span className="honest-table-star" aria-hidden>
                          ★
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="honest-cards">
          {SUPPORT_CARDS.map((card) => (
            <article key={card.id} className="honest-card agency-card">
              <div className="honest-card-icon">{card.icon}</div>
              <h3>{card.title}</h3>
              <p>{card.description}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
