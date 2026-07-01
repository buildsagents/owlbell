import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const rateLimitStore = new Map<string, { count: number; resetAt: number }>();
const RATE_LIMIT_WINDOW = 60_000;
const RATE_LIMIT_MAX = 30;

function rateLimit(ip: string): boolean {
  const now = Date.now();
  const entry = rateLimitStore.get(ip);
  if (!entry || now > entry.resetAt) {
    rateLimitStore.set(ip, { count: 1, resetAt: now + RATE_LIMIT_WINDOW });
    return true;
  }
  entry.count++;
  return entry.count <= RATE_LIMIT_MAX;
}

const CSP_HEADER_VALUE = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-eval' 'unsafe-inline' https://cdn.vercel-insights.com https://va.vercel-scripts.com https://*.retellai.com https://js.stripe.com",
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "img-src 'self' blob: data: https://*.stripe.com https://*.retellai.com",
  "font-src 'self' https://fonts.gstatic.com",
  "frame-src 'self' https://js.stripe.com https://hooks.stripe.com",
  "connect-src 'self' https://api.retellai.com https://*.retellai.com wss://*.retellai.com https://api.stripe.com https://o4507335808516096.ingest.us.sentry.io https://vitals.vercel-insights.com https://owlbell-api-production.up.railway.app wss://owlbell-api-production.up.railway.app",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Rewrite dashboard SPA routes to index.html
  if (pathname === "/app" || (pathname.startsWith("/app/") && !pathname.match(/\.\w+$/))) {
    const url = request.nextUrl.clone();
    url.pathname = "/app/index.html";
    return NextResponse.rewrite(url);
  }

  // Rate limit API routes
  if (pathname.startsWith("/api/")) {
    const ip = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim()
      ?? request.headers.get("x-real-ip")
      ?? "127.0.0.1";

    if (!rateLimit(ip)) {
      return new NextResponse(
        JSON.stringify({ error: "Too many requests", code: "RATE_LIMITED" }),
        { status: 429, headers: { "Content-Type": "application/json" } },
      );
    }
  }

  const response = NextResponse.next();

  // Security headers
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("X-Frame-Options", "DENY");
  response.headers.set("X-XSS-Protection", "1; mode=block");
  response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  response.headers.set("Content-Security-Policy", CSP_HEADER_VALUE);
  response.headers.set("Permissions-Policy", "camera=(), microphone=(self), geolocation=(), interest-cohort=()");
  response.headers.set("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload");

  return response;
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt).*)",
  ],
};
