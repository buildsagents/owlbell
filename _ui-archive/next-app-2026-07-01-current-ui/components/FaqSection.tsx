"use client";

import { useState } from "react";
import Link from "next/link";
import { TRUST_FAQ_IDS, FAQ_ITEMS } from "@/lib/faq-data";

const HOME_FAQ = FAQ_ITEMS.filter((item) =>
  TRUST_FAQ_IDS.includes(item.id as (typeof TRUST_FAQ_IDS)[number])
);

export default function FaqSection() {
  const [openId, setOpenId] = useState<string | null>(HOME_FAQ[0]?.id ?? null);

  return (
    <section className="section" id="faq">
      <div className="wrap">
        <div className="section-lead">
          <span className="section-label">FAQ</span>
          <h2>Common questions from plumbing owners.</h2>
          <p>Real company, managed setup, AI accuracy, and cancellation policies.</p>
        </div>
        <div className="faq-list">
          {HOME_FAQ.map((item) => {
            const isOpen = openId === item.id;
            return (
              <div key={item.id} className={`faq-item${isOpen ? " faq-item--open" : ""}`}>
                <button
                  type="button"
                  className="faq-trigger"
                  aria-expanded={isOpen}
                  onClick={() => setOpenId(isOpen ? null : item.id)}
                >
                  <span>{item.question}</span>
                  <span className="faq-icon" aria-hidden>+</span>
                </button>
                <div className="faq-panel" hidden={!isOpen}>
                  <p>{item.answer}</p>
                </div>
              </div>
            );
          })}
        </div>
        <div style={{ textAlign: "center", marginTop: "32px" }}>
          <Link href="/faq" className="btn btn--ghost">
            See all questions
          </Link>
        </div>
      </div>
    </section>
  );
}
