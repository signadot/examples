import { NextRequest, NextResponse } from 'next/server';

/**
 * Proxy route for Signadot sandbox requests (Alternative to Chrome Extension)
 * 
 * This route is used when NEXT_PUBLIC_USE_SIGNADOT_PROXY=true (default).
 * It adds the signadot-api-key header server-side to authenticate requests.
 * 
 * Alternative: Use the Signadot Chrome Extension (recommended) which injects
 * headers automatically, eliminating the need for this proxy route.
 * Set NEXT_PUBLIC_USE_SIGNADOT_PROXY=false to use the extension approach.
 */

/**
 * Backend API base URL
 * Set by GitHub Actions workflow from Signadot sandbox URL in preview environments.
 * Defaults to the local backend on port 8080 during local development.
 */
const BACKEND_API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

/**
 * Signadot API key for authenticating requests to Signadot preview URLs
 * Server-side only - set as SIGNADOT_API_KEY in Vercel (without NEXT_PUBLIC_ prefix)
 * Only needed when using the proxy approach (not needed with Chrome extension)
 */
const SIGNADOT_API_KEY = process.env.SIGNADOT_API_KEY || '';

function isSignadotUrl(url: string = BACKEND_API_URL): boolean {
  return url.includes('.preview.signadot.com') || url.includes('.sb.signadot.com');
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const resolvedParams = await params;
  return handleProxyRequest(request, resolvedParams, 'GET');
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const resolvedParams = await params;
  return handleProxyRequest(request, resolvedParams, 'POST');
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const resolvedParams = await params;
  return handleProxyRequest(request, resolvedParams, 'PUT');
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const resolvedParams = await params;
  return handleProxyRequest(request, resolvedParams, 'DELETE');
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const resolvedParams = await params;
  return handleProxyRequest(request, resolvedParams, 'PATCH');
}

async function handleProxyRequest(
  request: NextRequest,
  params: { path: string[] },
  method: string
) {
  try {
    const pathSegments = params.path || [];
    const backendPath = pathSegments.length > 0 
      ? `/${pathSegments.join('/')}` 
      : '/';
    
    const backendUrl = `${BACKEND_API_URL}${backendPath}`;
    const searchParams = request.nextUrl.searchParams.toString();
    const fullBackendUrl = searchParams 
      ? `${backendUrl}?${searchParams}` 
      : backendUrl;
    
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };
    
    if (isSignadotUrl() && SIGNADOT_API_KEY) {
      headers['signadot-api-key'] = SIGNADOT_API_KEY;
    }
    
    let body: string | undefined;
    if (['POST', 'PUT', 'PATCH'].includes(method)) {
      try {
        body = await request.text();
      } catch (error) {
        console.error('Failed to parse request body:', error);
      }
    }
    
    const backendResponse = await fetch(fullBackendUrl, {
      method,
      headers,
      body,
    });
    
    const responseData = await backendResponse.text();
    
    let jsonData;
    try {
      jsonData = JSON.parse(responseData);
    } catch {
      jsonData = responseData;
    }
    
    return NextResponse.json(jsonData, {
      status: backendResponse.status,
      headers: {
        'Content-Type': 'application/json',
        ...(backendResponse.headers.get('Access-Control-Allow-Origin') && {
          'Access-Control-Allow-Origin': backendResponse.headers.get('Access-Control-Allow-Origin')!,
        }),
      },
    });
  } catch (error) {
    console.error('Proxy request failed:', error);
    return NextResponse.json(
      { 
        error: 'Failed to proxy request to backend',
        message: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}
