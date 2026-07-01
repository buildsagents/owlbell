"use client";

type Props = {
  stepKey: string;
  title?: string;
};

const WALKTHROUGHS: Record<string, { title: string; src: string; caption: string }> = {
  business: {
    title: "Business basics (1 min)",
    src: "https://www.youtube.com/embed/ScMzIvxBSi4?rel=0",
    caption: "How your business name and service area shape your AI greeting.",
  },
  calls: {
    title: "Phone routing & hours (2 min)",
    src: "https://www.youtube.com/embed/ScMzIvxBSi4?rel=0",
    caption: "Forwarding vs new number, hours, and emergency escalation.",
  },
  ai: {
    title: "Voice & personality (1 min)",
    src: "https://www.youtube.com/embed/ScMzIvxBSi4?rel=0",
    caption: "Pick a voice and tone callers will hear on every line.",
  },
  knowledge: {
    title: "Knowledge base upload (2 min)",
    src: "https://www.youtube.com/embed/ScMzIvxBSi4?rel=0",
    caption: "Scripts, FAQs, and optional PDF uploads for RAG indexing.",
  },
  integrations: {
    title: "Calendar & CRM (1 min)",
    src: "https://www.youtube.com/embed/ScMzIvxBSi4?rel=0",
    caption: "Connect Google/Outlook and CRM handoff preferences.",
  },
  pricing: {
    title: "Plans & add-ons (1 min)",
    src: "https://www.youtube.com/embed/ScMzIvxBSi4?rel=0",
    caption: "Tier comparison, annual discount, and optional add-on packs.",
  },
  review: {
    title: "Go live (30 sec)",
    src: "https://www.youtube.com/embed/ScMzIvxBSi4?rel=0",
    caption: "Activation, inbound line assignment, and your first test call.",
  },
};

export default function OnboardingWalkthrough({ stepKey, title }: Props) {
  const video = WALKTHROUGHS[stepKey];
  if (!video) return null;

  return (
    <div className="ob-walkthrough" aria-label={`Video walkthrough: ${video.title}`}>
      <p className="ob-walkthrough-label">
        ▶ {title || video.title}
      </p>
      <div className="ob-walkthrough-frame">
        <iframe
          src={video.src}
          title={video.title}
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
        />
      </div>
      <p className="ob-muted ob-walkthrough-caption">{video.caption}</p>
    </div>
  );
}