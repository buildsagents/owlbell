import { NextResponse } from 'next/server';
import { createCheckoutSession } from '@/lib/stripe';
import { createClient } from '@/lib/supabase/server';
import { PlanTier } from '@/types';

export async function POST(request: Request) {
  try {
    const { plan } = await request.json() as { plan: Exclude<PlanTier, 'enterprise'> };

    // Get logged-in user's org
    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();

    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const { data: profile } = await supabase
      .from('profiles')
      .select('org_id')
      .eq('id', user.id)
      .single();

    if (!profile?.org_id) {
      return NextResponse.json({ error: 'No organization found' }, { status: 400 });
    }

    const baseUrl = process.env.NEXT_PUBLIC_APP_URL ?? 'https://owlbell.xyz';
    const url = await createCheckoutSession({
      plan,
      orgId: profile.org_id,
      customerEmail: user.email,
      successUrl: `${baseUrl}/dashboard?checkout=success`,
      cancelUrl: `${baseUrl}/#pricing`,
    });

    if (!url) {
      return NextResponse.json({ error: 'Could not create checkout session' }, { status: 500 });
    }

    return NextResponse.json({ url });
  } catch (error: any) {
    console.error('[stripe/checkout] Error:', error);
    return NextResponse.json({ error: error.message ?? 'Internal error' }, { status: 500 });
  }
}
