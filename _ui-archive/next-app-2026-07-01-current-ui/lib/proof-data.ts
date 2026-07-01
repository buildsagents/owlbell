export const PROOF_DISCLAIMER =
  "Demo flow based on real plumbing emergency intake patterns. Identifying details are anonymized and the public script is polished for clarity.";

export const PROOF_TESTIMONIAL_NOTE =
  "No named client testimonial yet - we're early. The summaries and SMS examples show the operating workflow with identifying details removed.";

export const DEMO_AUDIO_SRC = "/demos/plumbing-emergency-sample.mp3";

export const BEFORE_AFTER_METRICS = [
  {
    id: "missed",
    label: "After-hours calls to voicemail",
    before: "14/wk",
    after: "0/wk",
    delta: "Every overflow call answered",
  },
  {
    id: "answered",
    label: "Inbound calls answered",
    before: "71%",
    after: "100%",
    delta: "Under 2s pickup",
  },
  {
    id: "booked",
    label: "Jobs booked from missed-call capture",
    before: "3/mo",
    after: "9/mo",
    delta: "+6 booked jobs",
  },
  {
    id: "value",
    label: "Recovered job value (90 days)",
    before: "£0",
    after: "£18.4k",
    delta: "Anonymized pilot shop",
  },
] as const;

export const CALL_SUMMARIES = [
  {
    id: "emergency-intake",
    title: "After-hours emergency intake",
    location: "Bristol - after hours",
    metric: "Emergency demo flow",
    summary:
      "Caller reports a burst pipe with active water after hours. The receptionist classifies it as an emergency, captures address and callback details, and escalates to the on-call team.",
  },
  {
    id: "owner-dispatch",
    title: "Owner dispatch summary",
    location: "Post-call - automated",
    metric: "From live call analysis",
    summary:
      "Emergency flagged: active leak, occupant home, stopcock shut off but water remains. Service needed: burst pipe repair. Address and callback confirmed before routing.",
  },
  {
    id: "booked-outcome",
    title: "Booked job outcome",
    location: "Emergency dispatch",
    metric: "~£850 repair",
    summary:
      "On-call plumber receives the job summary immediately, with a follow-up slot held if further repair work is needed.",
  },
] as const;

export const BOOKED_JOB_SMS = [
  {
    id: "emergency-booked",
    time: "11:06 PM",
    context: "Fri - After hours",
    title: "Emergency - burst pipe",
    body: "Sarah M. - 24 Maple Road - active water - callback on file - ~£850 est.",
    chip: "Call answered in 1.8s",
  },
  {
    id: "owner-alert",
    time: "11:06 PM",
    context: "Emergency flagged",
    title: "Owlbell - new plumbing lead",
    body: "Burst pipe - Bristol BS6 - water pooling - callback confirmed - on-call routed",
    chip: "Instant owner SMS",
  },
] as const;

export const PROOF_TIMELINE = [
  { time: "11:04 PM", event: "Inbound call - burst pipe, basement flooding" },
  { time: "11:04 PM", event: "Answered in 1.8s, emergency flagged" },
  { time: "11:06 PM", event: "On-call plumber alerted, follow-up slot held" },
  { time: "11:06 PM", event: "Owner texted job summary + callback number" },
  { time: "8:30 AM", event: "Follow-up repair window ready if needed" },
] as const;
