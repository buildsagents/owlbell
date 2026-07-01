/**
 * Minimal homepage smoke test against a running Next.js server.
 * Run after: npm run build && npm run start
 */
import { chromium } from "playwright";

const BASE = process.env.VERIFY_BASE_URL || "http://localhost:3000";

async function main() {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));

  await page.goto(BASE, { waitUntil: "networkidle" });

  const hasLogo = (await page.locator(".owl-logo").count()) > 0;
  const hasHero = (await page.locator(".hero-dispatch").count()) > 0;
  const hasCalculator = (await page.locator(".roi-strip").count()) > 0;
  const bodyText = await page.locator("body").innerText();
  const hasHeadline = bodyText.includes("Stop Losing Emergency Plumbing Jobs After Hours");
  const hasSubheadline = bodyText.includes("before the customer calls the next plumber");
  const hasManagedPromise = bodyText.includes("Managed setup. No tech work");
  const hasPrimaryCta = bodyText.includes("Get Free Missed-Call Audit");

  console.log(`server: ${BASE}`);
  console.log(`logo_present: ${hasLogo}`);
  console.log(`hero_present: ${hasHero}`);
  console.log(`calculator_present: ${hasCalculator}`);
  console.log(`headline_present: ${hasHeadline}`);
  console.log(`subheadline_present: ${hasSubheadline}`);
  console.log(`managed_promise_present: ${hasManagedPromise}`);
  console.log(`primary_cta_present: ${hasPrimaryCta}`);
  console.log(`page_errors: ${errors.length === 0 ? "none" : errors.join("; ")}`);

  await browser.close();

  const failures: string[] = [];
  if (!hasLogo) failures.push("missing logo");
  if (!hasHero) failures.push("missing hero");
  if (!hasCalculator) failures.push("missing ROI calculator");
  if (!hasHeadline) failures.push("missing headline");
  if (!hasSubheadline) failures.push("missing subheadline");
  if (!hasManagedPromise) failures.push("missing managed setup promise");
  if (!hasPrimaryCta) failures.push("missing primary CTA");
  if (errors.length) failures.push(`page errors: ${errors.join("; ")}`);

  if (failures.length) {
    throw new Error(failures.join("; "));
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});