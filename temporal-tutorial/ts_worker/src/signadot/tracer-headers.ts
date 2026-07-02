/**
 * Helpers for reading the Signadot routing key out of the OpenTelemetry
 * context that the Temporal OTel interceptors store in task headers.
 *
 * IMPORTANT: this module is imported by the workflow interceptors, which run
 * inside the deterministic V8 workflow isolate. Everything in here must stay
 * pure and deterministic: no I/O, no Date/Math.random, no Node.js APIs.
 * `defaultPayloadConverter` from @temporalio/common is isolate-safe.
 */
import { defaultPayloadConverter } from '@temporalio/common';
import type { Headers } from '@temporalio/common';

/**
 * Header key used by the Temporal OpenTelemetry interceptors. The Python,
 * TypeScript, and Java SDKs all use the same key and carrier format (a JSON
 * text map with W3C `traceparent`/`baggage` entries), so workflows started by
 * the Python client are readable by this worker and vice versa.
 */
export const TRACE_HEADER = '_tracer-data';

export const ROUTING_KEY_BAGGAGE_KEY = 'sd-routing-key';

/**
 * Extract the Signadot routing key from the W3C `baggage` entry of the
 * serialized OTel context in Temporal task headers. Returns '' when absent.
 *
 * This is a plain string parse (not an OTel propagator) so that it can run
 * inside the workflow isolate.
 */
export function routingKeyFromHeaders(headers: Headers | undefined): string {
  const payload = headers?.[TRACE_HEADER];
  if (payload === undefined) {
    return '';
  }
  try {
    const carrier = defaultPayloadConverter.fromPayload<Record<string, string>>(payload);
    const baggage = carrier?.baggage;
    if (typeof baggage !== 'string') {
      return '';
    }
    for (const entry of baggage.split(',')) {
      // Entries look like `key=value` optionally followed by `;properties`
      const [pair] = entry.trim().split(';');
      const eq = pair.indexOf('=');
      if (eq === -1) {
        continue;
      }
      const key = pair.slice(0, eq).trim();
      if (key === ROUTING_KEY_BAGGAGE_KEY) {
        return decodeURIComponent(pair.slice(eq + 1).trim());
      }
    }
  } catch {
    // Malformed header: treat as no routing key
  }
  return '';
}
