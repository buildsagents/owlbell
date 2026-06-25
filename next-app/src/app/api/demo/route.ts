import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    console.log('Demo call request received:', body);

    // Placeholder: Trigger Vapi/Retell API calls here in the future
    // const response = await triggerProviderCall(body.phone, body.business);

    return NextResponse.json({
      success: true,
      message: 'Demo call triggered successfully (mocked)'
    });
  } catch (error: any) {
    console.error('Demo call error:', error);
    return NextResponse.json(
      { success: false, error: error.message || 'Internal server error' },
      { status: 500 }
    );
  }
}
