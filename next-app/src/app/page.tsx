"use client";

import { useState, useEffect, useCallback } from "react";
import MissedCallCalculator from "@/components/MissedCallCalculator";

const API = process.env.NEXT_PUBLIC_API_URL || "https://owlbell-api-production.up.railway.app";

/* ---------- Checkout Modal ---------- */
function CheckoutModal({
  open,
  onClose,
  plan,
  period = "monthly",
}: {
  open: boolean;
  onClose: () => void;
  plan: string;
  period?: string;
}) {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) document.body.style.overflow = "hidden";
    else {
      document.body.style.overflow = "";
      setEmail("");
      setError("");
    }
    return () => { document.body.style.overflow = ""; };
  }, [open]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/api/v1/billing/public-checkout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan, period, email }),
      });
      const data = await res.json();
      if (!data.success) throw new Error(data.message || "Checkout failed");
      window.location.href = data.data.url;
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  if (!open) return null;

  return (
    <div className="modal-overlay open" onClick={onClose}>
      <div className="modal-box" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose}>✕</button>
        <h3 style={{ marginTop: 0 }}>Get started with {plan === "basic" ? "Basic" : plan === "pro" ? "Pro" : "Pro Plus"}</h3>
        <p style={{ color: "var(--ink2)", marginBottom: 20 }}>
          Enter your email to continue to secure checkout. Your AI phone agent will be ready in about 1 day.
        </p>
        <form onSubmit={handleSubmit}>
          <input
            type="email"
            placeholder="Your email address"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            style={{ marginBottom: 12 }}
          />
          {error && <p style={{ color: "var(--danger)", fontSize: 14, marginBottom: 12 }}>{error}</p>}
          <button className="btn btn-primary" type="submit" disabled={loading} style={{ width: "100%" }}>
            {loading ? "Redirecting to Stripe…" : `Subscribe — $${plan === "basic" ? "297" : plan === "pro" ? "797" : "1,497"}/mo`}
          </button>
        </form>
        <p style={{ color: "var(--muted)", fontSize: 12, marginTop: 12, textAlign: "center" }}>
          Secure checkout powered by Stripe · Cancel anytime · No contracts
        </p>
      </div>
    </div>
  );
}

/* ---------- Reveal on Scroll ---------- */
function useReveal() {
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) entry.target.classList.add("visible");
        });
      },
      { threshold: 0.08 }
    );

    document.querySelectorAll(".reveal").forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);
}

/* =====================================================================
   PAGE
   ===================================================================== */
export default function HomePage() {
  const [headerScrolled, setHeaderScrolled] = useState(false);
  const [checkoutPlan, setCheckoutPlan] = useState<string | null>(null);

  useReveal();

  useEffect(() => {
    const onScroll = () => setHeaderScrolled(window.scrollY > 100);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const scrollTo = (id: string) => {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const openCheckout = (plan: string) => setCheckoutPlan(plan);

  return (
    <>
      {/* ---- HEADER ---- */}
      <header className={headerScrolled ? "scrolled" : ""}>
        <nav className="nav wrap">
          <div className="logo">Owl<span>bell</span></div>
          <div className="nav-cta">
            <button className="btn btn-sm btn-ghost hide-mobile" onClick={() => scrollTo("pricing")}>
              Pricing
            </button>
            <button className="btn btn-sm btn-primary" onClick={() => openCheckout("pro")}>
              Get Started
            </button>
          </div>
        </nav>
      </header>

      {/* ---- HERO ---- */}
      <section className="hero">
        <div className="wrap hero-grid">
          <div className="hero-left">
            <span className="eyebrow-alt" style={{ marginBottom: 16 }}>AI for tradesmen, built by tradesmen</span>
            <h1>
              You're Losing{" "}
              <span style={{ background: "var(--brand)", padding: "0 8px", display: "inline-block" }}>$45,000 a Year</span>{" "}
              to Missed Calls.
            </h1>
            <p className="sub">
              Owlbell answers every call in your business's name, books the
              appointment on your calendar, and texts you the details — 24/7.
              From $297/mo. No contracts.
            </p>
            <div className="hero-cta">
              <button className="btn btn-primary btn-lg" onClick={() => openCheckout("pro")}>
                Start Saving Missed Calls
              </button>
              <button className="btn btn-ghost btn-lg" onClick={() => scrollTo("how")}>
                See how it works →
              </button>
            </div>
            <div className="hero-trust">
              <div className="hero-trust-avatars">
                {["JM", "AK", "RL", "DT"].map((initials, i) => (
                  <div key={i}>{initials}</div>
                ))}
              </div>
              <p>
                <strong>250+ contractors</strong> trust Owlbell · <strong>4.9/5</strong> satisfaction
              </p>
            </div>
          </div>

          <div>
            <MissedCallCalculator />
          </div>
        </div>
      </section>

      {/* ---- INDUSTRY STRIPE ---- */}
      <div className="stripe-row" id="industries">
        {["HVAC", "PLUMBING", "ELECTRICAL", "ROOFING", "PEST CONTROL", "PROPERTY MGMT", "LANDSCAPING", "GUTTERS", "PAINTING", "FLOORING"].map((ind, i) => (
          <span key={i} className={`stripe-item ${i % 2 === 0 ? "" : "stripe-item-alt"}`}>
            {ind}
          </span>
        ))}
      </div>

      {/* ---- INDUSTRIES ---- */}
      <section className="section">
        <div className="wrap">
          <div className="section-header" style={{ textAlign: "center" }}>
            <span className="eyebrow">Built for your trade</span>
            <h2>Works the Same Way, No Matter What You Do</h2>
            <p>Every industry has the same problem — missed calls = lost revenue. Owlbell solves it the same way for all of them.</p>
          </div>
          <div className="ind-grid reveal">
            <div className="ind-card">
              <div className="ind-icon">❄️</div>
              <h3>HVAC</h3>
              <p>"My AC isn't cooling." Owlbell books the repair for tomorrow morning. You get the address and issue by text before the caller hangs up.</p>
            </div>
            <div className="ind-card">
              <div className="ind-icon">🔧</div>
              <h3>Plumbing</h3>
              <p>Burst pipe at 11pm? Owlbell detects the emergency, texts the on-call tech, and tells the caller help is on the way. No voicemail.</p>
            </div>
            <div className="ind-card">
              <div className="ind-icon">⚡</div>
              <h3>Electrical</h3>
              <p>"Can you look at my panel this week?" Owlbell checks the calendar, books the slot, sends a confirmation. No callbacks needed.</p>
            </div>
            <div className="ind-card">
              <div className="ind-icon">🏠</div>
              <h3>Roofing</h3>
              <p>Storm just passed. Every call is a potential job. Owlbell answers 3 calls at once, books inspections, captures leads that would've gone to voicemail.</p>
            </div>
            <div className="ind-card">
              <div className="ind-icon">🐛</div>
              <h3>Pest Control</h3>
              <p>Routine or emergency — Owlbell handles the "I see roaches" panic call and books the treatment without waking you up.</p>
            </div>
            <div className="ind-card">
              <div className="ind-icon">🌿</div>
              <h3>Landscaping</h3>
              <p>Spring rush is chaos. Owlbell catches the estimate requests, books consultations, and texts you the details while you're on the mower.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ---- PAIN / STATS ---- */}
      <section className="section" id="pain">
        <div className="wrap">
          <div className="section-header">
            <span className="eyebrow">The leak in your business</span>
            <h2>Every Missed Call Is a Job Your Competitor Books</h2>
            <p>
              When you're on a job, after hours, or the line's busy, callers
              don't leave voicemails. They hang up and dial the next guy.
            </p>
          </div>
          <div className="stat-grid reveal">
            <div className="stat-card">
              <div className="stat-num">85%</div>
              <p>of callers who hit voicemail <strong>never call back</strong></p>
            </div>
            <div className="stat-card">
              <div className="stat-num" style={{ color: "var(--brand)" }}>27-62%</div>
              <p>of inbound calls <strong>missed by contractors</strong> during peak season</p>
            </div>
            <div className="stat-card">
              <div className="stat-num" style={{ color: "var(--good)" }}>$1,200</div>
              <p>average revenue <strong>per emergency service call</strong></p>
            </div>
          </div>
          <p className="stat-note" style={{ marginTop: 32 }}>
            Sources: ServiceTitan · HomeAdvisor · Ruby Receptionist
          </p>
        </div>
      </section>

      {/* ---- HOW IT WORKS ---- */}
      <section className="section section-alt" id="how">
        <div className="wrap">
          <div className="section-header">
            <span className="eyebrow">How it works — the call flow</span>
            <h2>What Happens When a Call Comes In</h2>
            <p>From first ring to booked job. No voicemail, no hold, no missed revenue.</p>
          </div>
          <div className="steps reveal">
            <div className="step">
              <div className="step-num">1</div>
              <h4>📞 Call comes in — we answer in &lt;2s</h4>
              <p>The phone rings once. Owlbell picks up in your business's name — "<em>Thanks for calling Acme Plumbing, this is the after-hours line.</em>" The caller never hears a voicemail prompt or a hold message. They're talking to someone immediately.</p>
            </div>
            <div className="step">
              <div className="step-num">2</div>
              <h4>🧠 AI handles the conversation</h4>
              <p>Owlbell asks what they need, checks your calendar for availability, answers FAQs about pricing and service areas, and detects emergencies. It sounds natural — most callers don't realize it's AI.</p>
            </div>
            <div className="step">
              <div className="step-num">3</div>
              <h4>🗓️ Books the appointment</h4>
              <p>If the caller wants to book, Owlbell finds the next open slot on your calendar and confirms it on the call. The appointment is on your schedule before they hang up. No "I'll call you back."</p>
            </div>
            <div className="step">
              <div className="step-num">4</div>
              <h4>📱 You get a text instantly</h4>
              <p>Within seconds of the call ending, you receive a full summary — who called, what they needed, what was booked, and their contact info. You know everything before the caller hangs up. If it was an emergency, your on-call tech gets an immediate alert.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ---- FEATURES ---- */}
      <section className="section section-alt">
        <div className="wrap">
          <div className="section-header">
            <span className="eyebrow">What you get</span>
            <h2>Everything You Need to Never Miss Another Call</h2>
          </div>
          <div className="feat-grid reveal">
            <div className="feat-card feat-wide">
              <div className="feat-icon">📞</div>
              <h3>Answers Every Call, Instantly</h3>
              <p>Picks up in your business's name in under 2 seconds. No hold. No voicemail. Day, night, weekends, holidays. It catches the calls your voicemail loses.</p>
            </div>
            <div className="feat-card feat-huge">
              <div className="feat-stat">24/7</div>
              <div className="feat-stat-label">Coverage</div>
            </div>
            <div className="feat-card feat-huge">
              <div className="feat-stat">&lt;2s</div>
              <div className="feat-stat-label">Answer time</div>
            </div>
            <div className="feat-card">
              <div className="feat-icon">🗓️</div>
              <h3>Books Appointments</h3>
              <p>Checks your calendar, books the job, sends a confirmation text. No "I'll call you back."</p>
            </div>
            <div className="feat-card feat-wide">
              <div className="feat-icon">⚡</div>
              <h3>Texts You Instantly</h3>
              <p>Every call summary hits your phone the moment it ends — who called, what they needed, what was booked. You know before the caller hangs up.</p>
            </div>
            <div className="feat-card">
              <div className="feat-icon">🚨</div>
              <h3>Routes Emergencies</h3>
              <p>Detects urgent calls and transfers them to you or your on-call tech with full context. No phone tree.</p>
            </div>
            <div className="feat-card">
              <div className="feat-icon">🧠</div>
              <h3>Knows Your Business</h3>
              <p>Answers FAQs about hours, pricing, service areas, and more — trained on your actual info.</p>
            </div>
            <div className="feat-card">
              <div className="feat-icon">📊</div>
              <h3>Full Dashboard</h3>
              <p>Live transcripts, call recordings, captured leads, and analytics. See everything the AI handled.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ---- COMPARISON ---- */}
      <section className="section" id="compare">
        <div className="wrap">
          <div className="section-header">
            <span className="eyebrow">The math doesn't lie</span>
            <h2>Voicemail Costs You $62,400/Year. Owlbell Costs $297/Month.</h2>
          </div>
          <div className="reveal">
            <div className="cmp-wrap">
              <table className="cmp">
                <thead>
                  <tr>
                    <th></th>
                    <th>Voicemail</th>
                    <th>Answering Service</th>
                    <th className="own">Owlbell</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Monthly cost</td>
                    <td>$0</td>
                    <td>$800–$2,000</td>
                    <td className="own"><strong>$297</strong></td>
                  </tr>
                  <tr>
                    <td>Annual cost</td>
                    <td>$62,400*</td>
                    <td>$9,600–$24,000</td>
                    <td className="own"><strong>$3,564</strong></td>
                  </tr>
                  <tr>
                    <td>Answer time</td>
                    <td>Never</td>
                    <td>30s–3min hold</td>
                    <td className="own">&lt;2 seconds</td>
                  </tr>
                  <tr>
                    <td>Books appointments</td>
                    <td>—</td>
                    <td>Rarely</td>
                    <td className="own">✓ Onto your calendar</td>
                  </tr>
                  <tr>
                    <td>24/7 coverage</td>
                    <td>—</td>
                    <td>After-hours only</td>
                    <td className="own">✓ Always</td>
                  </tr>
                  <tr>
                    <td>Knows your business</td>
                    <td>—</td>
                    <td>Generic scripts</td>
                    <td className="own">✓ Trained on your info</td>
                  </tr>
                  <tr>
                    <td>Emergency routing</td>
                    <td>—</td>
                    <td>—</td>
                    <td className="own">✓ Instant escalation</td>
                  </tr>
                  <tr>
                    <td>Instant text alerts</td>
                    <td>—</td>
                    <td>Sometimes</td>
                    <td className="own">✓ Every call</td>
                  </tr>
                  <tr>
                    <td>Setup time</td>
                    <td>—</td>
                    <td>Days</td>
                    <td className="own">~1 day</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p style={{ color: "var(--muted)", fontSize: 12, marginTop: 12, textAlign: "center", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              *$62,400 = 10 missed calls/week × $300 avg job × 52 weeks. Your numbers may vary.
            </p>
          </div>
        </div>
      </section>

      {/* ---- TESTIMONIALS ---- */}
      <section className="section section-alt">
        <div className="wrap">
          <div className="section-header">
            <span className="eyebrow">Real contractors, real results</span>
            <h2>They Were Skeptical Too. Then the Jobs Started Booking.</h2>
          </div>
          <div className="testimonial-grid reveal">
            <div className="testimonial">
              <div className="testimonial-result">+22 missed calls recovered / mo</div>
              <blockquote>
                "I used to lose every after-hours call. Now I wake up to booked inspections. Paid for itself in week one."
              </blockquote>
              <div className="testimonial-head">
                <div className="testimonial-avatar">JM</div>
                <div>
                  <div className="testimonial-name">Jake Morrison</div>
                  <div className="testimonial-title">Owner, Lone Star Roofing · Round Rock, TX</div>
                </div>
              </div>
            </div>
            <div className="testimonial">
              <div className="testimonial-result">14 jobs booked in 30 days</div>
              <blockquote>
                "It books straight to my calendar while I'm under a sink. My old answering service just took messages I never called back."
              </blockquote>
              <div className="testimonial-head">
                <div className="testimonial-avatar">AK</div>
                <div>
                  <div className="testimonial-name">Alex Kwon</div>
                  <div className="testimonial-title">Owner, FlowRight Plumbing · Austin, TX</div>
                </div>
              </div>
            </div>
            <div className="testimonial">
              <div className="testimonial-result">$9,800 recovered pipeline</div>
              <blockquote>
                "Summer is chaos. Owlbell catches the no-AC calls I'd have missed and routes the real emergencies to my cell."
              </blockquote>
              <div className="testimonial-head">
                <div className="testimonial-avatar">RL</div>
                <div>
                  <div className="testimonial-name">Ray Lugo</div>
                  <div className="testimonial-title">Owner, coolAIR HVAC · Cedar Park, TX</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ---- PRICING ---- */}
      <section className="section" id="pricing">
        <div className="wrap">
          <div className="section-header">
            <span className="eyebrow">Simple pricing</span>
            <h2>Less Than One Missed Call Covers Your Entire Month.</h2>
            <p>One extra job pays for Basic four times over. No per-minute fees. No surprise charges.</p>
          </div>

          <div className="price-grid reveal">
            <div className="plan">
              <div className="plan-name">Basic</div>
              <div className="plan-amt">
                $297<span className="per">/mo</span>
              </div>
              <div className="plan-amt-sub">For solo contractors and small shops</div>
              <ul>
                <li>24/7 AI call answering</li>
                <li>Up to 500 calls/mo</li>
                <li>Voicemail → text + email</li>
                <li>Instant message alerts</li>
                <li>1 phone number</li>
                <li>Email support</li>
              </ul>
              <button className="btn btn-ghost" onClick={() => openCheckout("basic")}>
                Get Started
              </button>
            </div>

            <div className="plan featured">
              <div className="plan-name">Pro</div>
              <div className="plan-amt">
                $797<span className="per">/mo</span>
              </div>
              <div className="plan-amt-sub">For growing teams — books appointments automatically</div>
              <ul>
                <li>Everything in Basic</li>
                <li>Up to 2,000 calls/mo</li>
                <li>Appointment booking + calendar sync</li>
                <li>CRM integration &amp; call routing</li>
                <li>Analytics dashboard</li>
                <li>Up to 3 phone numbers</li>
                <li>Priority same-day support</li>
              </ul>
              <button className="btn btn-primary" onClick={() => openCheckout("pro")}>
                Get Pro
              </button>
            </div>

            <div className="plan">
              <div className="plan-name">Enterprise</div>
              <div className="plan-amt">
                Custom<span className="per"></span>
              </div>
              <div className="plan-amt-sub">For multi-location and high-volume operations</div>
              <ul>
                <li>Everything in Pro</li>
                <li>Unlimited calls</li>
                <li>Multi-location setup</li>
                <li>Advanced AI agents</li>
                <li>White-label option</li>
                <li>Dedicated account manager</li>
                <li>SLA guarantee</li>
              </ul>
              <button className="btn btn-ghost" onClick={() => window.location.href = "mailto:buildsagents@gmail.com?subject=Owlbell Enterprise Inquiry"}>
                Email us
              </button>
            </div>
          </div>

          <p style={{ color: "var(--muted)", textAlign: "center", marginTop: 20, fontSize: 14, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Pro Plus: $1,497/mo for unlimited calls · Overage $0/call (truly unlimited) · Annual = 2 months free
          </p>

          <div className="offer reveal">
            <span className="eyebrow-alt" style={{ marginBottom: 4 }}>Founding client offer — limited spots</span>
            <h2>50% Off Your First 3 Months. Setup Waived.</h2>
            <div className="offer-stats">
              <div className="offer-stat">
                <span className="offer-stat-num">50%</span>
                <span className="offer-stat-label">off first 3 months</span>
              </div>
              <div className="offer-stat">
                <span className="offer-stat-num">$0</span>
                <span className="offer-stat-label">setup fee</span>
              </div>
              <div className="offer-stat">
                <span className="offer-stat-num">~1 day</span>
                <span className="offer-stat-label">to go live</span>
              </div>
            </div>
            <p style={{ color: "var(--ink2)", maxWidth: "55ch", margin: "20px auto 0", fontSize: 16, lineHeight: 1.5 }}>
              We're onboarding <strong>20 founding clients</strong> in exchange for a short testimonial once you see results.
              That's <strong style={{ color: "var(--brand)" }}>$148/mo on Basic</strong> or{" "}
              <strong style={{ color: "var(--brand)" }}>$398/mo on Pro</strong> — locked in for life.
            </p>
            <div style={{ marginTop: 24 }}>
              <button className="btn btn-primary btn-lg" onClick={() => openCheckout("pro")}>
                Claim a Founding Spot →
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* ---- GUARANTEE ---- */}
      <section className="section section-alt">
        <div className="wrap guarantee reveal">
          <div className="guarantee-icon">🛡️</div>
          <h2>5 Jobs in 30 Days or Your Next Month Is Free.</h2>
          <p>
            If Owlbell doesn't book you at least 5 extra jobs in your first 30 days, we'll give you
            the next month free. No questions. No fine print. We're that confident.
          </p>
          <button className="btn btn-primary btn-lg" onClick={() => openCheckout("pro")}>
            Get Started Risk-Free
          </button>
          <p style={{ marginTop: 16, color: "var(--muted)", fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Month-to-month · Cancel anytime · No contracts
          </p>
        </div>
      </section>

      {/* ---- FAQ ---- */}
      <section className="section">
        <div className="wrap">
          <div className="section-header">
            <span className="eyebrow">Questions</span>
            <h2>You're Probably Wondering…</h2>
          </div>
          <div className="faq reveal" style={{ maxWidth: 700, margin: "0 auto" }}>
            <details>
              <summary>Does it actually sound human?</summary>
              <p>Yes. Most people cannot tell they are talking to AI. You can test it yourself after subscribing — we'll send you a demo number to call and hear it live.</p>
            </details>
            <details>
              <summary>Do I need to talk to anyone to get started?</summary>
              <p>Nope. Pick a plan, pay, and you will receive dashboard access within 24 hours. Everything is handled from your dashboard — no phone calls, no sales pitch, no meetings.</p>
            </details>
            <details>
              <summary>Do I have to change my phone number?</summary>
              <p>No. The fastest setup keeps your existing number — you just forward calls to Owlbell when you are busy, after hours, or do not pick up. We can also port your number later if you want.</p>
            </details>
            <details>
              <summary>What if it cannot answer something?</summary>
              <p>It captures the caller's details and routes to you (or your on-call tech) per your rules — and texts you immediately. It never leaves a caller stuck.</p>
            </details>
            <details>
              <summary>How much work is setup for me?</summary>
              <p>About 15 minutes. After subscribing, you will get a dashboard link where you configure your business hours, services, and FAQs. The AI does the rest. Live in about a day.</p>
            </details>
            <details>
              <summary>What does it cost, really? Any surprise fees?</summary>
              <p>Flat monthly ($297 Basic / $797 Pro / $1,497 Pro Plus). Basic covers 500 calls — most contractors use 200–300. Pro covers 2,000. Pro Plus is truly unlimited. Overage if you exceed your plan is $0.50/call. No per-minute charges. No hidden fees.</p>
            </details>
            <details>
              <summary>What if I want to cancel?</summary>
              <p>Month-to-month. Cancel anytime from your dashboard. Plus a 30-day guarantee — if it does not book you 5 extra jobs in your first month, the next month is free. No risk.</p>
            </details>
            <details>
              <summary>What if I already have an answering service?</summary>
              <p>Most just take a message. Owlbell books the appointment onto your calendar and texts you instantly — no per-minute bill. Worth a 10-minute comparison.</p>
            </details>
            <details>
              <summary>How is this different from just using ChatGPT?</summary>
              <p>Owlbell is purpose-built for phone calls — it handles real-time voice, books appointments on your actual calendar, routes emergencies, and integrates with your CRM. ChatGPT cannot pick up your phone. Plus our team monitors and improves it monthly.</p>
            </details>
            <details>
              <summary>Are calls recorded? Is my data private?</summary>
              <p>Recording is optional with proper disclosure (we handle consent rules by state). Your customer data is not sold or shared. See our Privacy Policy.</p>
            </details>
          </div>
        </div>
      </section>

      {/* ---- FINAL CTA ---- */}
      <section className="section section-alt">
        <div className="wrap" style={{ textAlign: "center" }}>
          <div className="reveal">
            <span className="eyebrow-alt" style={{ marginBottom: 12 }}>Ready to stop losing calls?</span>
            <h2 style={{ fontSize: "clamp(32px, 3.8vw, 48px)", letterSpacing: "-0.03em", lineHeight: 1.05, margin: "12px auto", maxWidth: "16ch" }}>
              Start Answering Every Call. Live in ~1 Day.
            </h2>
            <p style={{ color: "var(--ink2)", maxWidth: "55ch", margin: "0 auto 32px", fontSize: 18, lineHeight: 1.5 }}>
              No setup calls. No sales pitch. Pick a plan, pay securely, and get your dashboard within 24 hours.
            </p>
            <div style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap" }}>
              <button className="btn btn-primary btn-lg" onClick={() => openCheckout("pro")}>
                Get Started Now
              </button>
              <button className="btn btn-ghost btn-lg" onClick={() => scrollTo("pricing")}>
                Compare Plans
              </button>
            </div>
            <p style={{ marginTop: 20, color: "var(--muted)", fontSize: 13, fontWeight: 600 }}>
              Questions? Email{" "}
              <a href="mailto:buildsagents@gmail.com" style={{ color: "var(--ink)", fontWeight: 800, textDecoration: "underline" }}>
                buildsagents@gmail.com
              </a>
              {" · "}Response in &lt; 2 hours
            </p>
          </div>
        </div>
      </section>

      {/* ---- FOOTER ---- */}
      <footer>
        <div className="wrap footer-grid">
          <div className="footer-col">
            <div className="logo" style={{ marginBottom: 12 }}>Owl<span>bell</span></div>
            <p style={{ maxWidth: 280 }}>24/7 AI phone answering for local service businesses. Backed by a human expert team.</p>
          </div>
          <div className="footer-col">
            <h4>Product</h4>
            <a href="#pricing" onClick={(e) => { e.preventDefault(); scrollTo("pricing"); }}>Pricing</a>
            <a href="#how" onClick={(e) => { e.preventDefault(); scrollTo("how"); }}>How it works</a>
            <button className="btn btn-sm btn-ghost" style={{ marginTop: 8, display: "inline-flex" }} onClick={() => openCheckout("pro")}>
              Get Started
            </button>
          </div>
          <div className="footer-col">
            <h4>Industries</h4>
            <span className="footer-item">HVAC</span>
            <span className="footer-item">Plumbing</span>
            <span className="footer-item">Electrical</span>
            <span className="footer-item">Roofing</span>
            <span className="footer-item">Pest Control</span>
            <span className="footer-item">Property Mgmt</span>
          </div>
          <div className="footer-col">
            <h4>Contact</h4>
            <a href="mailto:buildsagents@gmail.com">buildsagents@gmail.com</a>
            <p>Response in &lt; 2 hours</p>
          </div>
        </div>
        <div className="wrap footer-bottom">
          © {new Date().getFullYear()} Owlbell. All rights reserved.
        </div>
      </footer>

      {/* ---- CHECKOUT MODAL ---- */}
      {checkoutPlan && (
        <CheckoutModal
          open={!!checkoutPlan}
          onClose={() => setCheckoutPlan(null)}
          plan={checkoutPlan}
        />
      )}

      {/* ---- MOBILE CTA BAR ---- */}
      <div className="mobile-bar">
        <button className="btn btn-ghost" onClick={() => scrollTo("pricing")}>
          Pricing
        </button>
        <button className="btn btn-primary" onClick={() => openCheckout("pro")}>
          Get Started
        </button>
      </div>
    </>
  );
}
