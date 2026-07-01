export type PlumbingScenario = {
  id: string;
  label: string;
  urgency: "emergency" | "urgent" | "routine";
  avgValue: string;
  afterHours: boolean;
};

export const PLUMBING_SCENARIOS: PlumbingScenario[] = [
  {
    id: "burst-pipe",
    label: "Burst pipe - basement flooding",
    urgency: "emergency",
    avgValue: "~£850",
    afterHours: true,
  },
  {
    id: "sewer-backup",
    label: "Sewer backup - main line",
    urgency: "emergency",
    avgValue: "~£1,200",
    afterHours: true,
  },
  {
    id: "water-heater",
    label: "Water heater - no hot water",
    urgency: "urgent",
    avgValue: "~£640",
    afterHours: true,
  },
  {
    id: "drain-clog",
    label: "Drain clog - kitchen sink",
    urgency: "routine",
    avgValue: "~£320",
    afterHours: false,
  },
  {
    id: "slab-leak",
    label: "Slab leak - active moisture",
    urgency: "urgent",
    avgValue: "~£1,450",
    afterHours: true,
  },
];

export type DispatchRow = {
  id: string;
  time: string;
  caller: string;
  issue: string;
  status: "booked" | "emergency" | "callback" | "answered";
  value: string;
  address?: string;
};

export const DISPATCH_LIVE_ROWS: DispatchRow[] = [
  {
    id: "live-1",
    time: "11:04 PM",
    caller: "Sarah M.",
    issue: "Burst pipe - active water",
    status: "booked",
    value: "£850",
    address: "24 Maple Road",
  },
  {
    id: "live-2",
    time: "9:18 PM",
    caller: "R. K.",
    issue: "Sewer backup - main line",
    status: "emergency",
    value: "~£1,200",
    address: "18 Victoria St",
  },
  {
    id: "live-3",
    time: "6:42 PM",
    caller: "D. P.",
    issue: "Drain clog - kitchen sink",
    status: "answered",
    value: "£320",
    address: "7 Clifton Vale",
  },
  {
    id: "live-4",
    time: "2:15 PM",
    caller: "M. L.",
    issue: "Water heater - no hot water",
    status: "callback",
    value: "~£640",
    address: "Callback queued",
  },
];
