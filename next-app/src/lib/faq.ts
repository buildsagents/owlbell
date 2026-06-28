export const SITE_URL = "https://owlbell.xyz";

export type FaqItem = {
  question: string;
  answer: string;
};

export const FAQ_ITEMS: FaqItem[] = [
  {
    question: "What is Owlbell?",
    answer:
      "Owlbell is a managed reception agency for US plumbing contractors. We answer inbound calls 24/7, qualify leads, book appointments, and text job details to the owner — not software you configure yourself.",
  },
  {
    question: "Who is Owlbell for?",
    answer:
      "Owlbell serves plumbing contractors only. We specialize in emergency call handling, after-hours routing, and booking workflows built for plumbing shops.",
  },
  {
    question: "What are the pricing tiers?",
    answer:
      "Launch is $1,497/month for 24/7 answering and owner alerts. Growth is $4,997/month plus a one-time setup fee for booking, CRM handoff, and dedicated success support. Scale starts at $9,997/month for multi-location shops and custom SLAs. Every plan includes a 7-day trial.",
  },
  {
    question: "Is there a free trial?",
    answer:
      "Yes. Every plan includes a 7-day trial with white-glove onboarding. You can cancel during the trial period.",
  },
  {
    question: "How do I get started?",
    answer:
      "Subscribe to a plan, complete the onboarding intake at owlbell.xyz/onboarding, and your specialist builds scripts and routing. Most shops go live within two days.",
  },
  {
    question: "How do I contact Owlbell?",
    answer:
      "Email hello@owlbell.xyz. We typically reply within a few hours. Phone support is not available yet.",
  },
];

export function buildFaqPageJsonLd(items: FaqItem[]) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: items.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: item.answer,
      },
    })),
  };
}

export function buildServiceJsonLd() {
  return {
    "@context": "https://schema.org",
    "@type": "Service",
    name: "Owlbell Managed Reception",
    url: SITE_URL,
    description:
      "Managed reception agency for US plumbing contractors. We answer, book, and text job details — 24/7.",
    provider: {
      "@type": "Organization",
      name: "Owlbell",
      url: SITE_URL,
      email: "hello@owlbell.xyz",
    },
    areaServed: {
      "@type": "Country",
      name: "United States",
    },
    serviceType: "Managed reception for plumbing contractors",
    offers: [
      {
        "@type": "Offer",
        name: "Launch",
        price: "1497",
        priceCurrency: "USD",
        description: "24/7 answering, emergency routing, owner alerts",
      },
      {
        "@type": "Offer",
        name: "Growth",
        price: "4997",
        priceCurrency: "USD",
        description: "Booking workflow, CRM handoff, dedicated success contact",
      },
      {
        "@type": "Offer",
        name: "Scale",
        price: "9997",
        priceCurrency: "USD",
        description: "Multi-location, custom SLAs, dedicated success lead",
      },
    ],
  };
}