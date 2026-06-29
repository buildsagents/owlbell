/** Pure ROI math for marketing calculator — testable without React. */

export type RoiInputs = {
  missedPerWeek: number;
  avgJobValue: number;
  monthlyPlanCost?: number;
};

export type RoiResult = {
  recoveredMonthly: number;
  breakevenDays: number | null;
};

export function computeRoi({
  missedPerWeek,
  avgJobValue,
  monthlyPlanCost = 1497,
}: RoiInputs): RoiResult {
  const recoveredMonthly = Math.max(0, missedPerWeek * 4 * avgJobValue);
  let breakevenDays: number | null = null;
  if (recoveredMonthly > monthlyPlanCost) {
    const daily = recoveredMonthly / 30;
    breakevenDays = Math.max(1, Math.ceil(monthlyPlanCost / daily));
  }
  return { recoveredMonthly, breakevenDays };
}

export function buildOnboardingQueryFromRoi(result: RoiResult, inputs: RoiInputs): string {
  const params = new URLSearchParams();
  params.set("source", "roi");
  params.set("missed", String(inputs.missedPerWeek));
  params.set("job_value", String(inputs.avgJobValue));
  params.set("recovered", String(Math.round(result.recoveredMonthly)));
  return params.toString();
}