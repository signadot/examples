/**
 * Backend API base URL
 * Set by GitHub Actions workflow from Signadot sandbox URL in preview environments.
 * Defaults to the local backend on port 8080 during local development.
 */
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

/**
 * Whether to use the proxy route for Signadot URLs
 * 
 * Two methods for accessing Signadot sandboxes:
 * 1. Chrome Extension (Recommended): Set NEXT_PUBLIC_USE_SIGNADOT_PROXY=false
 *    - Frontend calls the existing app URL (ingress / LB / staging / local URL)
 *    - Chrome extension injects routing headers automatically
 *    - No code changes needed, works for developers with extension installed
 * 
 * 2. Proxy Route (Alternative): Set NEXT_PUBLIC_USE_SIGNADOT_PROXY=true (default)
 *    - Frontend calls /api/proxy/... which adds signadot-api-key header server-side
 *    - Requires SIGNADOT_API_KEY in Vercel environment variables
 *    - Works for reviewers without extension, enables automated testing
 * 
 * Defaults to true (proxy) for backward compatibility
 */
const USE_SIGNADOT_PROXY = 
  process.env.NEXT_PUBLIC_USE_SIGNADOT_PROXY !== 'false';

/**
 * Checks if the API URL is a Signadot preview URL
 */
export function isSignadotUrl(url: string = API_URL): boolean {
  return url.includes('.preview.signadot.com') || url.includes('.sb.signadot.com');
}

/**
 * Creates a full API endpoint URL
 * 
 * For Signadot URLs:
 * - If using proxy: routes through /api/proxy/... (adds API key server-side)
 * - If using Chrome extension: returns the configured app URL; extension handles routing headers
 * 
 * For non-Signadot URLs (production/local): returns direct URL
 */
export function getApiUrl(endpoint: string): string {
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint.slice(1) : endpoint;
  
  if (isSignadotUrl()) {
    if (USE_SIGNADOT_PROXY) {
      // Proxy route adds Signadot API key header server-side
      return `/api/proxy/${cleanEndpoint}`;
    } else {
      // Chrome extension approach: use existing app URL
      // Extension injects routing headers automatically
      const baseUrl = API_URL.endsWith('/') ? API_URL.slice(0, -1) : API_URL;
      return `${baseUrl}/${cleanEndpoint}`;
    }
  }
  
  const baseUrl = API_URL.endsWith('/') ? API_URL.slice(0, -1) : API_URL;
  return `${baseUrl}/${cleanEndpoint}`;
}

/**
 * Gets the headers to include in API requests
 * 
 * For Signadot URLs:
 * - Proxy approach: Headers handled server-side by proxy route
 * - Chrome extension: Extension injects headers, no special headers needed here
 * 
 * For non-Signadot URLs: Standard JSON content type
 */
export function getApiHeaders(additionalHeaders: Record<string, string> = {}): HeadersInit {
  return {
    'Content-Type': 'application/json',
    ...additionalHeaders,
  };
}
