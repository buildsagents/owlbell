/**
 * Capture a full-page homepage screenshot.
 * Prereq: npm run build && npm run start (or VERIFY_BASE_URL pointing at running app)
 */
import { chromium } from "playwright";
import { mkdirSync } from "fs";
import { dirname, resolve } from "path";

const BASE = process.env.VERIFY_BASE_URL || "http://localhost:3000";
const OUT = resolve(__dirname, "../../../gtm/collateral/owlbell-homepage-full.png");

async function main() {
  mkdirSync(dirname(OUT), { recursive: true });

  const browser = await chromium.launch();
  const page = await browser.newPage({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  });

  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.waitForTimeout(300);
  await page.screenshot({ path: OUT, fullPage: true });

  console.log(`Screenshot saved: ${OUT}`);
  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});