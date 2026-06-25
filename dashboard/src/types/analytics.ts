// ───────────────────────────────────────────────────────────
// Analytics Types
// ───────────────────────────────────────────────────────────

export type AnalyticsPeriod = "today" | "week" | "month" | "quarter" | "year" | "custom";

export interface CallMetrics {
  totalCalls: number;
  totalChange: number;
  answeredCalls: number;
  answeredChange: number;
  missedCalls: number;
  missedChange: number;
  avgDuration: number;
  avgDurationChange: number;
  avgWaitTime: number;
  avgWaitTimeChange: number;
  resolutionRate: number;
  resolutionRateChange: number;
}

export interface HourlyCallData {
  hour: number;
  calls: number;
  answered: number;
  missed: number;
}

export interface DailyCallData {
  date: string;
  calls: number;
  answered: number;
  missed: number;
  avgDuration: number;
}

export interface CallOutcomeBreakdown {
  outcome: string;
  count: number;
  percentage: number;
}

export interface TopCaller {
  phoneNumber: string;
  name: string | null;
  callCount: number;
  totalDuration: number;
}

export interface AnalyticsResponse {
  metrics: CallMetrics;
  hourlyData: HourlyCallData[];
  dailyData: DailyCallData[];
  outcomeBreakdown: CallOutcomeBreakdown[];
  topCallers: TopCaller[];
  period: AnalyticsPeriod;
  dateRange: { from: string; to: string };
}
