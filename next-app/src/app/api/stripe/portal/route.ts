import { NextResponse } from 'next/server';
import { createPortalSession } from '@/lib/stripe';

export async function POST(request: Request) {
  try {
    const { customerId } = await request.json();
    const baseUrl = process.env.NEXT_PUBLIC_APP_URL ?? 'https://owlbell.xyz';

    const url = await createPortalSession({
      customerId,
      returnUrl: `${baseUrl}/dashboard/billing`,
    });

    if (!url) {
      return NextResponse.json({ error: 'Could not create portal session' }, { status: 500 });
    }

    return NextResponse.json({ url });
  } catch (error: any) {
    return NextResponse.json({ error: error.message ?? 'Internal error' }, { status: 500 });
  }
}
