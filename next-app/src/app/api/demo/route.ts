import { NextResponse } from 'next/server';

export async function POST() {
  return NextResponse.json(
    {
      success: false,
      error: "deprecated_demo_route",
      message: "Use /api/demo/web-call to mint a Retell web-call token for the live demo.",
      use: "/api/demo/web-call",
    },
    { status: 410 }
  );
}
