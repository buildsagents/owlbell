export const SITE_URL = "https://owlbell.xyz";

export type FaqItem = {
  question: string;
  answer: string;
};

export const FAQ_ITEMS: FaqItem[] = [
  {
    question: "What is Owlbell?",
    answer:
      "Owlbell is a self-serve AI receptionist for US service businesses — plumbing, HVAC, electrical, dental, legal, and more. You configure voice, scripts, and routing in onboarding; we answer inbound calls 24/7, book appointments, and text job details to you.",
  },
  {
    question: "Who is Owlbell for?",
    answer:
      "Owlbell serves established US service businesses that cannot afford to miss calls — especially after hours. Shops with meaningful call volume and average job values above ~$300 see the fastest ROI.",
  },
  {
    question: "What are the pricing tiers?",
    answer:
      "Launch is $1,497/month for 24/7 answering and owner alerts. Growth is $4,997/month plus a one-time setup fee for booking, CRM handoff, and dedicated success support. Scale starts at $9,997/month for multi-location shops and custom SLAs. Every plan includes a 7-day trial.",
  },
  {
    question: "Is there a free trial?",
    answer:
      "Yes. Start at owlbell.xyz/onboarding — fully self-serve, no sales call required. Every paid plan includes a 7-day trial. Cancel during the trial if coverage is not a fit.",
  },
  {
    question: "How do I get started?",
    answer:
      "Go to owlbell.xyz/onboarding, complete the self-serve wizard (voice, scripts, calendar, forwarding), and place your first test call to your Owlbell inbound line. Most owners finish in under 15 minutes.",
  },
  {
    question: "How do I contact Owlbell?",
    answer:
      "Email hello@owlbell.xyz. We typically reply within a few hours on business days. Chat and email support are included; phone sales calls are not required.",
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
    name: "Owlbell AI Receptionist",
    url: SITE_URL,
    description:
      "Self-serve AI receptionist for US service businesses. Answer, book, and text job details — 24/7.",
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
    serviceType: "AI phone answering for service businesses",
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