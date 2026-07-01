"use client";

import { useMemo, useState } from "react";
import FaqAccordion from "@/components/FaqAccordion";
import type { FaqItem } from "@/lib/faq-data";

type Props = {
  items: FaqItem[];
};

export default function FaqSearch({ items }: Props) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (item) =>
        item.question.toLowerCase().includes(q) || item.answer.toLowerCase().includes(q),
    );
  }, [items, query]);

  return (
    <div className="faq-search-wrap">
      <label className="faq-search-label" htmlFor="faq-search">
        Search FAQ
      </label>
      <input
        id="faq-search"
        className="faq-search-input"
        type="search"
        placeholder="Real company, AI mistakes, Jobber, cancel, after hours..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      {filtered.length === 0 ? (
        <p className="faq-search-empty">No matches - try a shorter keyword or email hello@owlbell.xyz</p>
      ) : (
        <FaqAccordion items={filtered} />
      )}
    </div>
  );
}