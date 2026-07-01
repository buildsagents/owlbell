export const SITE_URL = "https://owlbell.xyz";

export type FaqItem = {
  question: string;
  answer: string;
};

export const FAQ_ITEMS: FaqItem[] = [
  {
    question: "What is Owlbell?",
    answer:
      "Owlbell is a managed AI receptionist agency for UK plumbing companies. We configure voice, scripts, emergency routing, and owner alerts; you forward missed calls; we answer inbound 24/7, book qualified jobs, and text job details to you.",
  },
  {
    question: "Who is Owlbell for?",
    answer:
      "Owlbell serves established UK plumbing shops that cannot afford to miss calls, especially after hours. Companies with meaningful call volume and average job values above ~£250 see the fastest ROI.",
  },
  {
    question: "What are the pricing tiers?",
    answer:
      "Launch is £1,197/month for 24/7 answering and owner alerts. Growth is £3,997/month plus a one-time setup fee for booking, CRM handoff, and dedicated success support. Scale starts at £7,997/month for multi-location shops and custom SLAs. Every plan includes a 7-day trial.",
  },
  {
    question: "Is there a free trial?",
    answer:
      "Yes. Start at owlbell.xyz/onboarding - managed setup, no tech work required. Every paid plan includes a 7-day trial. Cancel during the trial if coverage is not a fit.",
  },
  {
    question: "How do I get started?",
    answer:
      "Go to owlbell.xyz/onboarding, start your trial, and share your shop details. Our team configures voice, scripts, calendar, and forwarding - then you forward missed calls and start getting booked jobs by SMS.",
  },
  {
    question: "How do I contact Owlbell?",
    answer:
      "Email hello@owlbell.xyz. We typically reply within a few hours on UK business days. Chat and email support are included; phone sales calls are not required.",
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
      "Managed AI receptionist for UK plumbing companies. Answer, book, and text job details - 24/7.",
    provider: {
      "@type": "Organization",
      name: "Owlbell",
      url: SITE_URL,
      email: "hello@owlbell.xyz",
    },
    areaServed: {
      "@type": "Country",
      name: "United Kingdom",
    },
    serviceType: "AI phone answering for plumbing companies",
    offers: [
      {
        "@type": "Offer",
        name: "Launch",
        price: "1197",
        priceCurrency: "GBP",
        description: "24/7 answering, emergency routing, owner alerts",
      },
      {
        "@type": "Offer",
        name: "Growth",
        price: "3997",
        priceCurrency: "GBP",
        description: "Booking workflow, CRM handoff, dedicated success contact",
      },
      {
        "@type": "Offer",
        name: "Scale",
        price: "7997",
        priceCurrency: "GBP",
        description: "Multi-location, custom SLAs, dedicated success lead",
      },
    ],
  };
}