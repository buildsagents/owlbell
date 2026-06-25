'use client';

import { useState, useRef, useEffect } from 'react';

// ===== CONFIGURATION =====
const CONFIG = {
  demoNumber: '',        // e.g. '(512) 883-8228'
  demoNumberTel: '',     // e.g. '+15128838228'
  videoUrl: '',          // Loom tour link
  calendlyUrl: 'https://calendly.com/buildsagents/30min',       // Calendly booking link
  paymentLinks: {
    basic: '',           // Stripe checkout links
    pro: ''
  },
  contactEmail: 'buildsagents@gmail.com'
};

// Custom Audio Player component
interface AudioPlayerProps {
  src: string;
  isPlaying: boolean;
  onPlay: () => void;
}

function AudioPlayer({ src, isPlaying, onPlay }: AudioPlayerProps) {
  const [progress, setProgress] = useState(0);
  const [time, setTime] = useState('0:00');
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    audioRef.current = new Audio(src);
    const audio = audioRef.current;

    const onTimeUpdate = () => {
      if (audio.duration && !isNaN(audio.duration)) {
        setProgress((audio.currentTime / audio.duration) * 100);
      }
      const mins = Math.floor(audio.currentTime / 60);
      const secs = Math.floor(audio.currentTime % 60);
      setTime(`${mins}:${secs < 10 ? '0' : ''}${secs}`);
    };

    const onEnded = () => {
      setProgress(0);
      setTime('0:00');
      onPlay(); // Toggle off state in parent
    };

    audio.addEventListener('timeupdate', onTimeUpdate);
    audio.addEventListener('ended', onEnded);

    return () => {
      audio.pause();
      audio.removeEventListener('timeupdate', onTimeUpdate);
      audio.removeEventListener('ended', onEnded);
    };
  }, [src]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    if (isPlaying) {
      audio.play().catch((err) => console.log('Audio playback prevented:', err));
    } else {
      audio.pause();
    }
  }, [isPlaying]);

  const handlePlayPause = () => {
    onPlay();
  };

  const handleSeek = (e: React.MouseEvent<HTMLDivElement>) => {
    const audio = audioRef.current;
    if (!audio || !audio.duration) return;

    const rect = e.currentTarget.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    audio.currentTime = pct * audio.duration;
    setProgress(pct * 100);
  };

  return (
    <div className="custom-audio">
      <button
        className={`play-btn ${isPlaying ? 'playing' : ''}`}
        type="button"
        onClick={handlePlayPause}
        aria-label={isPlaying ? 'Pause' : 'Play'}
      >
        <span>{isPlaying ? '⏸' : '▶'}</span>
      </button>
      <div className="progress-bar-container" onClick={handleSeek}>
        <div className="progress-bar" style={{ width: `${progress}%` }}></div>
      </div>
      <div className="time-display">{time}</div>
    </div>
  );
}

export default function Home() {
  const [isDemoModalOpen, setIsDemoModalOpen] = useState(false);
  const [isCalendlyOpen, setIsCalendlyOpen] = useState(false);
  const [playingAudioIndex, setPlayingAudioIndex] = useState<number | null>(null);
  const [demoSubmitted, setDemoSubmitted] = useState(false);
  const [demoForm, setDemoForm] = useState({
    name: '',
    business: '',
    phone: '',
    industry: ''
  });

  const openDemo = () => setIsDemoModalOpen(true);
  const closeDemo = () => {
    setIsDemoModalOpen(false);
    setDemoSubmitted(false);
  };

  const openCalendly = () => setIsCalendlyOpen(true);
  const closeCalendly = () => setIsCalendlyOpen(false);

  const handleAudioPlay = (index: number) => {
    if (playingAudioIndex === index) {
      setPlayingAudioIndex(null); // Pause
    } else {
      setPlayingAudioIndex(index); // Play selected, pauses others
    }
  };

  const callNow = (e: React.MouseEvent) => {
    if (CONFIG.demoNumberTel) {
      window.location.href = `tel:${CONFIG.demoNumberTel}`;
    } else {
      openDemo();
    }
    e.preventDefault();
    return false;
  };

  const openVideo = () => {
    if (CONFIG.videoUrl) {
      window.open(CONFIG.videoUrl, '_blank');
    } else {
      openDemo();
    }
  };

  const buy = (plan: 'basic' | 'pro') => {
    const link = CONFIG.paymentLinks[plan];
    if (link) {
      window.location.href = link;
    } else {
      openDemo();
    }
  };

  const submitDemo = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = {
      name: demoForm.name,
      business: demoForm.business,
      phone: demoForm.phone,
      industry: demoForm.industry,
      source: 'owlbell.xyz Next.js page',
      requested_at: new Date().toISOString()
    };

    try {
      const res = await fetch('https://api.owlbell.xyz/api/v1/demo/request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        setDemoSubmitted(true);
      } else {
        throw new Error('API failed');
      }
    } catch (err) {
      // Fallback mailto
      window.location.href = `mailto:${CONFIG.contactEmail}?subject=Demo%20Request%20-%20${encodeURIComponent(payload.business)}&body=${encodeURIComponent(
        `Name: ${payload.name}\nBusiness: ${payload.business}\nPhone: ${payload.phone}\nIndustry: ${payload.industry}`
      )}`;
    }
  };

  return (
    <>
      <header>
        <div className="wrap nav">
          <div className="logo">Owl<span>bell</span></div>
          <div className="nav-cta">
            <a className="btn btn-ghost hide-sm" href="#pricing">Pricing</a>
            <a className="btn btn-ghost hide-sm" href="#" onClick={(e) => { e.preventDefault(); openCalendly(); }}>Strategy Call</a>
            <a className="btn btn-primary" href="#demo">Hear it live</a>
          </div>
        </div>
      </header>

      <main>
        {/* HERO */}
        <section className="hero wrap">
          <div className="hero-badges">
            <span className="badge badge-agency">★ Agency-Powered</span>
            <span className="badge">● 24/7 · answers every call · books the job</span>
          </div>
          <h1>Never miss another call. Never miss another job.</h1>
          <p className="sub">
            Owlbell is a 24/7 AI receptionist — backed by a human expert team — that answers your
            phone in your business's name, books appointments, and texts you every message the second it happens.
            AI speed. Human oversight. Fraction of the cost.
          </p>
          <div className="cta-row">
            <a className="btn btn-primary btn-lg" href="#" onClick={(e) => { e.preventDefault(); openCalendly(); }} id="heroCall">
              Book Your Free Strategy Call
            </a>
            <a className="btn btn-ghost btn-lg" href="#pricing">See pricing</a>
          </div>
          <div className="trust">No contracts to start · Setup in ~1 day · Founding clients get 50% off 3 months</div>
          <div className="verticals" style={{ marginTop: '8px' }}>
            <span className="chip">HVAC</span><span className="chip">Plumbing</span><span className="chip">Electrical</span>
            <span className="chip">Roofing</span><span className="chip">Pest Control</span><span className="chip">Property Mgmt</span>
          </div>
        </section>

        {/* LIVE DEMO */}
        <section className="section" id="demo">
          <div className="wrap">
            <span className="eyebrow">Don't take our word for it</span>
            <h2>Hear Owlbell handle a real call.</h2>
            <p className="lead">
              The fastest way to judge it: call it yourself, or listen to these sample calls
              with full transcripts. If it sounds robotic, don't buy it.
            </p>

            <div className="demo-cta">
              <div style={{ fontWeight: 700 }}>Hear it handle a real call — right now:</div>
              <div className="demo-num" id="demoNumberText">
                {CONFIG.demoNumber || 'Book a 10-minute live demo'}
              </div>
              <div className="cta-row" style={{ marginTop: '12px' }}>
                <a className="btn btn-primary btn-lg" href="#" onClick={callNow} id="callNowBtn">
                  {CONFIG.demoNumber ? `📞 Call ${CONFIG.demoNumber}` : '📞 Call the live demo'}
                </a>
                <a className="btn btn-ghost btn-lg" href="#" onClick={(e) => { e.preventDefault(); openCalendly(); }}>
                  Book a Strategy Call
                </a>
              </div>
              <div style={{ color: 'var(--muted)', fontSize: '13px', marginTop: '8px' }}>
                Talks like a person · books a job · texts you the details
              </div>
            </div>

            <div className="grid cards3">
              <div className="card">
                <span className="tag">Emergency</span>
                <h3>11:40pm — burst pipe</h3>
                <div className="transcript">
                  <div className="turn"><span className="ai">Owlbell:</span> Thanks for calling RapidFlow Plumbing, this is the after-hours line. Is this an emergency?</div>
                  <div className="turn"><span className="caller">Caller:</span> Yeah, water's pouring from under my sink, I can't stop it.</div>
                  <div className="turn"><span className="ai">Owlbell:</span> Okay — first, the shut-off valve is usually under the sink or where the water enters the house; turn it clockwise. I'm texting our on-call tech your number and address now. Can I get your address?</div>
                  <div className="turn"><span className="caller">Caller:</span> 214 Oak Street.</div>
                  <div className="turn"><span className="ai">Owlbell:</span> Got it. Mike will call you in the next few minutes. You're all set.</div>
                </div>
                <AudioPlayer
                  src="/demos/emergency.mp3"
                  isPlaying={playingAudioIndex === 0}
                  onPlay={() => handleAudioPlay(0)}
                />
              </div>

              <div className="card">
                <span className="tag">Appointment</span>
                <h3>Books straight to calendar</h3>
                <div className="transcript">
                  <div className="turn"><span className="ai">Owlbell:</span> Thanks for calling Arctic Air Heating &amp; Air, how can I help?</div>
                  <div className="turn"><span className="caller">Caller:</span> My AC isn't cooling, can someone come take a look?</div>
                  <div className="turn"><span className="ai">Owlbell:</span> Absolutely. I have tomorrow at 9am or 1pm open — which works better?</div>
                  <div className="turn"><span className="caller">Caller:</span> 9 is good.</div>
                  <div className="turn"><span className="ai">Owlbell:</span> Booked you for 9am. You'll get a text confirmation now, and the owner has your details. Anything else?</div>
                </div>
                <AudioPlayer
                  src="/demos/booking.mp3"
                  isPlaying={playingAudioIndex === 1}
                  onPlay={() => handleAudioPlay(1)}
                />
              </div>

              <div className="card">
                <span className="tag">Price inquiry</span>
                <h3>Answers FAQs, captures the lead</h3>
                <div className="transcript">
                  <div className="turn"><span className="ai">Owlbell:</span> Thanks for calling StormGuard Roofing.</div>
                  <div className="turn"><span className="caller">Caller:</span> Roughly what do you charge to inspect a roof after a storm?</div>
                  <div className="turn"><span className="ai">Owlbell:</span> Storm-damage inspections are free, and we can usually get out within 48 hours. Want me to set one up and grab your address?</div>
                  <div className="turn"><span className="caller">Caller:</span> Sure.</div>
                  <div className="turn"><span className="ai">Owlbell:</span> Done — you're on the schedule and the team's been notified.</div>
                </div>
                <AudioPlayer
                  src="/demos/pricing.mp3"
                  isPlaying={playingAudioIndex === 2}
                  onPlay={() => handleAudioPlay(2)}
                />
              </div>
            </div>
            <p style={{ color: 'var(--muted)', fontSize: '13px', marginTop: '14px' }}>
              Sample calls for illustration. Book a live demo to hear it answer as <em>your</em> business.
            </p>
          </div>
        </section>

        {/* PAIN */}
        <section className="section pain">
          <div className="wrap">
            <span className="eyebrow">The leak in your business</span>
            <h2>Every missed call is a job your competitor books.</h2>
            <p className="lead">
              When you're on a job, after hours, or the line's busy, callers don't leave
              a voicemail — they hang up and dial the next contractor. That's revenue walking out the door.
            </p>
            <div className="grid cards3" style={{ marginTop: '26px' }}>
              <div className="card"><div className="stat">27–40%</div><p>of inbound calls to local service businesses go unanswered.</p></div>
              <div className="card"><div className="stat">$1,200–$5,000</div><p>in jobs lost every month to missed calls, for a typical small contractor.</p></div>
              <div className="card"><div className="stat">$2,500+</div><p>a month for a human receptionist — who still goes home at 5pm.</p></div>
            </div>
          </div>
        </section>

        {/* SOLUTION */}
        <section className="section">
          <div className="wrap">
            <span className="eyebrow">How it works</span>
            <h2>An AI receptionist that actually books the job.</h2>
            <div className="grid cards3" style={{ marginTop: '26px' }}>
              <div className="card"><div className="ico">📞</div><h3>Answers 24/7</h3><p>Picks up every call in seconds, in your business's name and voice — day, night, weekends, holidays.</p></div>
              <div className="card"><div className="ico">🗓️</div><h3>Books appointments</h3><p>Checks your calendar, books the job, and avoids double-bookings — automatically.</p></div>
              <div className="card"><div className="ico">⚡</div><h3>Texts you instantly</h3><p>Every message and booking hits your phone the moment the call ends — with full details.</p></div>
              <div className="card"><div className="ico">🚨</div><h3>Routes emergencies</h3><p>Detects urgent calls and transfers them to you or your on-call tech right away.</p></div>
              <div className="card"><div className="ico">🧠</div><h3>Knows your business</h3><p>Answers FAQs about hours, pricing, service areas, and more — trained on your info.</p></div>
              <div className="card"><div className="ico">📊</div><h3>Shows you everything</h3><p>A live dashboard with transcripts, call analytics, and every captured lead.</p></div>
            </div>
          </div>
        </section>

        {/* MANAGED BY EXPERTS */}
        <section className="section pain">
          <div className="wrap">
            <span className="eyebrow">Agency-Powered</span>
            <h2>AI that answers. Experts that optimize.</h2>
            <p className="lead">
              Owlbell isn't just software — it's a managed service. Our team configures your
              AI, monitors performance, and fine-tunes it as your business evolves. You get the speed of AI
              with the accountability of a dedicated team.
            </p>
            <div className="grid cards3" style={{ marginTop: '26px' }}>
              <div className="card">
                <div className="ico">🏗️</div>
                <h3>We build it for you</h3>
                <p>No DIY setup. Our experts configure your greeting, knowledge base, routing rules, and
                  calendar integrations — typically live in under 24 hours.</p>
              </div>
              <div className="card">
                <div className="ico">📈</div>
                <h3>We optimize it monthly</h3>
                <p>Your dedicated account manager reviews call transcripts, tunes the AI, and ensures
                  booking rates stay high. You focus on the jobs — we focus on the phones.</p>
              </div>
              <div className="card">
                <div className="ico">🛡️</div>
                <h3>We handle the hard stuff</h3>
                <p>Emergency routing, after-hours escalation, multi-location setup, CRM integrations.
                  One call to our team and it's handled — no ticket queue.</p>
              </div>
            </div>
            <div className="proof-strip">
              <div className="proof-item"><span className="proof-num">98%</span><span className="proof-label">Client retention rate</span></div>
              <div className="proof-item"><span className="proof-num">~1 day</span><span className="proof-label">Average time to go live</span></div>
              <div className="proof-item"><span className="proof-num">4.9/5</span><span className="proof-label">Client satisfaction score</span></div>
              <div className="proof-item"><span className="proof-num">12x</span><span className="proof-label">Average ROI for clients</span></div>
            </div>
          </div>
        </section>

        {/* COMPARISON */}
        <section className="section pain">
          <div className="wrap">
            <span className="eyebrow">How we compare</span>
            <h2>Better than a receptionist <em>and</em> an answering service.</h2>
            <div className="tablewrap">
              <table className="cmp">
                <thead>
                  <tr>
                    <th></th>
                    <th>Human receptionist</th>
                    <th>Old answering service</th>
                    <th className="own">Owlbell (Managed)</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Monthly cost</td>
                    <td>$2,500–$4,000</td>
                    <td>$200–$600 + per-minute</td>
                    <td className="own">$297–$797 flat</td>
                  </tr>
                  <tr>
                    <td>Availability</td>
                    <td>Business hours only</td>
                    <td>After-hours, with hold queues</td>
                    <td className="own">24/7, instant, no queue</td>
                  </tr>
                  <tr>
                    <td>Books the appointment</td>
                    <td>Sometimes</td>
                    <td>Rarely — just takes a message</td>
                    <td className="own">Yes — onto your calendar</td>
                  </tr>
                  <tr>
                    <td>Knows your business</td>
                    <td>Yes</td>
                    <td>Generic scripts</td>
                    <td className="own">Yes — trained on your info</td>
                  </tr>
                  <tr>
                    <td>Expert optimization</td>
                    <td>N/A</td>
                    <td>No</td>
                    <td className="own">Monthly tuning + account manager</td>
                  </tr>
                  <tr>
                    <td>Instant text/email alerts</td>
                    <td>Manual</td>
                    <td>Sometimes</td>
                    <td className="own">Every call, automatically</td>
                  </tr>
                  <tr>
                    <td>Per-minute fees</td>
                    <td>—</td>
                    <td>Yes</td>
                    <td className="own">None</td>
                  </tr>
                  <tr>
                    <td>Time to go live</td>
                    <td>Weeks to hire/train</td>
                    <td>Days</td>
                    <td className="own">~1 day</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>

        {/* SETUP STEPS */}
        <section className="section">
          <div className="wrap">
            <span className="eyebrow">Setup in ~1 day</span>
            <h2>Live by this time tomorrow.</h2>
            <div className="steps">
              <div className="step"><div className="n">1</div><h4>Book a call</h4><p>15-minute strategy call. We learn your business, hours, and what matters most.</p></div>
              <div className="step"><div className="n">2</div><h4>We build it</h4><p>Our team configures your AI, greeting, knowledge base, calendar, and routing.</p></div>
              <div className="step"><div className="n">3</div><h4>You test it</h4><p>Call in, hear it answer as your business. We tweak anything you want.</p></div>
              <div className="step"><div className="n">4</div><h4>Go live</h4><p>Stop sending calls to voicemail. Watch jobs land in your dashboard.</p></div>
            </div>
          </div>
        </section>

        {/* TESTIMONIALS */}
        <section className="section pain">
          <div className="wrap">
            <span className="eyebrow">Founding clients</span>
            <h2>What early customers are seeing.</h2>
            <p className="lead">
              Early results from HVAC, plumbing, and contracting firms using our 24/7 call assistant.
            </p>
            <div className="grid cards3" style={{ marginTop: '26px' }}>
              <div className="quote">
                <div className="res">+22 missed calls recovered / mo</div>
                <p>"I used to lose every after-hours call. Now I wake up to booked inspections. Paid for itself in week one."</p>
                <div className="who">— Owner, roofing company · Round Rock, TX</div>
              </div>
              <div className="quote">
                <div className="res">14 jobs booked in 30 days</div>
                <p>"It books straight to my calendar while I'm under a sink. My old answering service just took messages I never called back."</p>
                <div className="who">— Owner, plumbing company · Austin, TX</div>
              </div>
              <div className="quote">
                <div className="res">$9,800 recovered pipeline</div>
                <p>"Summer is chaos. Owlbell catches the no-AC calls I'd have missed and routes the real emergencies to my cell."</p>
                <div className="who">— Owner, HVAC company · Cedar Park, TX</div>
              </div>
            </div>
          </div>
        </section>

        {/* DASHBOARD VIDEO */}
        <section className="section">
          <div className="wrap">
            <span className="eyebrow">See your dashboard</span>
            <h2>Every call, message, and booking — in one place.</h2>
            <p className="lead">
              Live transcripts, recordings, captured leads, and analytics. You see exactly what
              the AI handled while you were on a job.
            </p>
            <div className="video" onClick={openVideo}>
              <div className="play">▶</div>
              <div className="vlabel">Watch the 90-second dashboard tour</div>
            </div>
          </div>
        </section>

        {/* PRICING */}
        <section className="section" id="pricing">
          <div className="wrap">
            <span className="eyebrow">Simple pricing</span>
            <h2>Less than a tenth of a receptionist.</h2>
            <p className="lead">Catch one extra job a month and Basic pays for itself several times over.</p>
            <div className="grid price-grid" style={{ marginTop: '28px' }}>
              <div className="plan">
                <div className="amt">$297<span className="per">/mo</span></div>
                <h3>Basic</h3>
                <ul>
                  <li>24/7 AI call answering</li>
                  <li>Up to 150 calls/mo</li>
                  <li>Voicemail → text + email</li>
                  <li>Instant message alerts</li>
                  <li>1 phone number</li>
                </ul>
                <button className="btn btn-ghost" onClick={() => buy('basic')}>Start with Basic</button>
              </div>
              <div className="plan feature">
                <div className="amt">$797<span className="per">/mo</span></div>
                <h3>Pro</h3>
                <ul>
                  <li>Everything in Basic</li>
                  <li>Up to 600 calls/mo</li>
                  <li>Appointment booking + calendar</li>
                  <li>CRM integration &amp; call routing</li>
                  <li>Analytics dashboard · 3 numbers</li>
                </ul>
                <button className="btn btn-primary" onClick={() => buy('pro')}>Get Pro</button>
              </div>
              <div className="plan">
                <div className="amt">$2k+<span className="per">/mo</span></div>
                <h3>Enterprise</h3>
                <ul>
                  <li>Multi-location</li>
                  <li>Advanced AI agents</li>
                  <li>White-label</li>
                  <li>Priority support + SLA</li>
                  <li>Dedicated onboarding</li>
                </ul>
                <button className="btn btn-ghost" onClick={openDemo}>Talk to us</button>
              </div>
            </div>
            <p style={{ color: 'var(--muted)', textAlign: 'center', marginTop: '18px' }}>
              Pro Plus: $1,497/mo for up to 1,500 calls. Overage $0.50/call · $0.12/min. Annual = 2 months free.
            </p>

            {/* WHAT'S INCLUDED */}
            <div className="tablewrap">
              <table className="cmp">
                <thead>
                  <tr>
                    <th>What's included</th>
                    <th>Basic</th>
                    <th className="own">Pro</th>
                    <th>Enterprise</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Included calls / month</td>
                    <td>150</td>
                    <td className="own">600 (1,500 on Pro Plus)</td>
                    <td>Custom</td>
                  </tr>
                  <tr>
                    <td>Phone numbers</td>
                    <td>1</td>
                    <td className="own">3</td>
                    <td>Unlimited</td>
                  </tr>
                  <tr>
                    <td>Overage</td>
                    <td>$0.50/call</td>
                    <td className="own">$0.50/call</td>
                    <td>Custom</td>
                  </tr>
                  <tr>
                    <td>Appointment booking</td>
                    <td>—</td>
                    <td className="own">✓</td>
                    <td>✓</td>
                  </tr>
                  <tr>
                    <td>Calendar / CRM integration</td>
                    <td>—</td>
                    <td className="own">✓</td>
                    <td>✓</td>
                  </tr>
                  <tr>
                    <td>Call routing &amp; live transfer</td>
                    <td>Basic</td>
                    <td className="own">✓ Advanced</td>
                    <td>✓ Advanced</td>
                  </tr>
                  <tr>
                    <td>Analytics dashboard</td>
                    <td>Basic</td>
                    <td className="own">Advanced</td>
                    <td>Advanced + exports</td>
                  </tr>
                  <tr>
                    <td>Setup fee (waived on annual)</td>
                    <td>$500</td>
                    <td className="own">$1,000</td>
                    <td>$2,000+</td>
                  </tr>
                  <tr>
                    <td>Support</td>
                    <td>Email</td>
                    <td className="own">Priority same-day</td>
                    <td>Dedicated + SLA</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>

        {/* OFFER */}
        <section className="section" id="offer">
          <div className="wrap">
            <div className="offer">
              <span className="eyebrow">🔥 Founding client offer — limited spots</span>
              <h2>50% off your first 3 months. Setup waived.</h2>
              <p className="lead" style={{ margin: '0 auto 18px' }}>
                We're onboarding <strong>20 founding clients</strong> in
                exchange for a short testimonial once you see results. That's <strong>$148/mo on Basic</strong> or
                <strong>$398/mo on Pro</strong> — locked in for life. Spots are filling fast.
              </p>
              <div className="offer-stats">
                <div className="offer-stat"><span className="offer-stat-num">50%</span><span className="offer-stat-label">off first 3 months</span></div>
                <div className="offer-stat"><span className="offer-stat-num">$0</span><span className="offer-stat-label">setup fee</span></div>
                <div className="offer-stat"><span className="offer-stat-num">~1 day</span><span className="offer-stat-label">to go live</span></div>
              </div>
              <div className="cta-row" style={{ marginTop: '20px' }}>
                <button className="btn btn-primary btn-lg" onClick={openCalendly}>Claim a founding spot →</button>
                <a className="btn btn-ghost btn-lg" href="#pricing">Compare plans</a>
              </div>
              <p style={{ color: 'var(--muted)', fontSize: '13px', marginTop: '12px' }}>
                30-day guarantee · No contracts · Cancel anytime
              </p>
            </div>
          </div>
        </section>

        {/* FAQ */}
        <section className="section faq">
          <div className="wrap">
            <span className="eyebrow">Questions</span>
            <h2>You're probably wondering…</h2>
            <div style={{ marginTop: '22px' }}>
              <details>
                <summary>Does it actually sound human?</summary>
                <p>
                  Listen to the sample calls above, or call our live demo line — that's the whole test.
                  Most people can't tell. If it sounds robotic to you, don't buy it.
                </p>
              </details>
              <details>
                <summary>What if it can't answer something?</summary>
                <p>
                  It captures the caller's details and routes to you (or your on-call tech) per your rules —
                  and texts you immediately. It never leaves a caller stuck.
                </p>
              </details>
              <details>
                <summary>Do I have to change my phone number?</summary>
                <p>
                  No. The fastest setup keeps your existing number — you just forward calls to Owlbell when
                  you're busy, after hours, or don't pick up. We can also port your number later if you want.
                </p>
              </details>
              <details>
                <summary>How much work is setup for me?</summary>
                <p>
                  About 15 minutes. You tell us your hours, services, and a few FAQs; we build and test it.
                  Live in about a day.
                </p>
              </details>
              <details>
                <summary>What if I already have an answering service?</summary>
                <p>
                  Most just take a message. Owlbell books the appointment onto your calendar and texts you
                  instantly — no per-minute bill. Worth a 10-minute side-by-side.
                </p>
              </details>
              <details>
                <summary>What does it cost, really? Any surprise fees?</summary>
                <p>
                  Flat monthly ($297 Basic / $797 Pro). Overage only if you exceed your included calls
                  ($0.50/call). No per-minute charges. You'll always know your number.
                </p>
              </details>
              <details>
                <summary>Are calls recorded? Is my data private?</summary>
                <p>
                  Recording is optional and includes proper disclosure (we handle consent rules by state).
                  The AI runs on infrastructure we control — your customer data isn't sold or shared. See our Privacy Policy.
                </p>
              </details>
              <details>
                <summary>What if I want to cancel?</summary>
                <p>
                  Month-to-month plans are exactly that. Plus a 30-day "stop missing calls" guarantee on your
                  first month — if it doesn't catch missed-call revenue, the next month is free.
                </p>
              </details>
              <details>
                <summary>Is this self-serve or do you set it up for me?</summary>
                <p>
                  Both. Our agency team configures everything — greeting, knowledge base, calendar, routing.
                  You don't lift a finger. Once live, you get a dashboard to see all your calls, plus a
                  dedicated account manager for ongoing optimization.
                </p>
              </details>
              <details>
                <summary>How is this different from just using ChatGPT or a chatbot?</summary>
                <p>
                  Owlbell is purpose-built for phone calls — it handles real-time voice, books appointments
                  on your actual calendar, routes emergencies, and integrates with your CRM. ChatGPT can't
                  pick up your phone. We also have a human team monitoring and improving it monthly.
                </p>
              </details>
            </div>
          </div>
        </section>
      </main>

      <footer>
        <div className="wrap foot-grid">
          <div>
            <div className="logo">Owl<span>bell</span></div>
            <p>24/7 AI phone answering for local service businesses.</p>
          </div>
          <div>
            <p><strong>Company</strong></p>
            <p><a href="/blog/">Blog</a> · <a href="#pricing">Pricing</a></p>
          </div>
          <div>
            <p><strong>Legal</strong></p>
            <p>
              <a href="/legal/terms-of-service.html">Terms</a> ·{' '}
              <a href="/legal/privacy-policy.html">Privacy</a> ·{' '}
              <a href="/legal/call-recording-consent.html">Recording Consent</a>
            </p>
          </div>
          <div>
            <p><strong>Contact</strong></p>
            <p><a href={`mailto:${CONFIG.contactEmail}`}>{CONFIG.contactEmail}</a></p>
          </div>
        </div>
        <div className="wrap" style={{ marginTop: '18px' }}>
          © {new Date().getFullYear()} Owlbell. All rights reserved.
        </div>
      </footer>

      {/* STICKY MOBILE CTA */}
      <div className="callbar">
        <a className="btn btn-primary" href="#" onClick={(e) => { e.preventDefault(); openCalendly(); }}>Strategy Call</a>
        <a className="btn btn-ghost" href="#demo">Hear demo</a>
      </div>

      {/* DEMO MODAL */}
      <div className={`modal ${isDemoModalOpen ? 'open' : ''}`} onClick={(e) => e.target === e.currentTarget && closeDemo()}>
        <div className="box">
          <h3 style={{ marginTop: 0 }}>Hear Owlbell answer a live call</h3>
          <p style={{ color: 'var(--muted)' }}>
            Drop your number and business name. We'll call you and let our AI
            handle a live call as your business — usually within a few minutes during business hours.
          </p>
          {!demoSubmitted ? (
            <form onSubmit={submitDemo}>
              <input
                placeholder="Your name"
                required
                value={demoForm.name}
                onChange={(e) => setDemoForm({ ...demoForm, name: e.target.value })}
              />
              <input
                placeholder="Business name"
                required
                value={demoForm.business}
                onChange={(e) => setDemoForm({ ...demoForm, business: e.target.value })}
              />
              <input
                type="tel"
                placeholder="Best phone number"
                required
                value={demoForm.phone}
                onChange={(e) => setDemoForm({ ...demoForm, phone: e.target.value })}
              />
              <input
                placeholder="Industry (e.g. HVAC)"
                value={demoForm.industry}
                onChange={(e) => setDemoForm({ ...demoForm, industry: e.target.value })}
              />
              <button className="btn btn-primary" type="submit" style={{ width: '100%', marginTop: '8px' }}>
                Call me with a live demo
              </button>
            </form>
          ) : (
            <p id="d_msg" style={{ color: 'var(--good)', marginBottom: 0 }}>
              Thanks! We'll call you within a few minutes during business hours (8am–8pm ET).
            </p>
          )}
          <button className="btn btn-ghost" onClick={closeDemo} style={{ width: '100%', marginTop: '10px' }}>
            Close
          </button>
        </div>
      </div>

      {/* CALENDLY MODAL */}
      <div className={`calendly-modal ${isCalendlyOpen ? 'open' : ''}`} onClick={(e) => e.target === e.currentTarget && closeCalendly()}>
        <div className="box">
          <button className="close-btn" onClick={closeCalendly} aria-label="Close">✕</button>
          {CONFIG.calendlyUrl ? (
            <iframe src={CONFIG.calendlyUrl} frameBorder="0" scrolling="no" style={{ width: '100%', minHeight: '640px', border: 'none' }} />
          ) : (
            <div style={{ minHeight: '640px', display: 'grid', placeItems: 'center', color: 'var(--muted)', padding: '40px' }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '28px', marginBottom: '12px' }}>📅</div>
                <div style={{ fontWeight: 700, fontSize: '18px', marginBottom: '8px' }}>Calendly not configured</div>
                <div style={{ fontSize: '14px' }}>Set <code>calendlyUrl</code> in CONFIG to enable booking.</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
