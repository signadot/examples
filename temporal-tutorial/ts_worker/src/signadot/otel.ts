/**
 * OpenTelemetry plumbing for the Node.js side of the worker/client.
 * Platform-owned: application activities never import OTel APIs directly.
 *
 * `setupOpenTelemetry` registers a context manager (so `context.with()`
 * scoping works) and the W3C trace-context + baggage propagators (so
 * `propagation.inject/extract` carry the `sd-routing-key` baggage). This is
 * intentionally minimal: if you already run the OTel NodeSDK
 * (`@opentelemetry/sdk-node`), it does both of these for you and additionally
 * auto-instruments HTTP clients so outbound requests from activities carry
 * `traceparent` and `baggage` headers automatically.
 */
import { context, propagation, Context } from '@opentelemetry/api';
import { AsyncLocalStorageContextManager } from '@opentelemetry/context-async-hooks';
import { CompositePropagator, W3CTraceContextPropagator, W3CBaggagePropagator } from '@opentelemetry/core';
import { defaultPayloadConverter } from '@temporalio/common';
import type { Headers } from '@temporalio/common';
import { TRACE_HEADER } from './tracer-headers';

let done = false;

export function setupOpenTelemetry(): void {
  if (done) {
    return;
  }
  context.setGlobalContextManager(new AsyncLocalStorageContextManager().enable());
  propagation.setGlobalPropagator(
    new CompositePropagator({
      propagators: [new W3CTraceContextPropagator(), new W3CBaggagePropagator()],
    })
  );
  done = true;
}

/**
 * Deserialize the OTel context (trace context + baggage) stored in Temporal
 * task headers under `_tracer-data`. Node.js side only -- inside the workflow
 * isolate use the pure helpers from tracer-headers.ts instead.
 */
export function contextFromHeaders(headers: Headers | undefined): Context | undefined {
  const payload = headers?.[TRACE_HEADER];
  if (payload === undefined) {
    return undefined;
  }
  try {
    const carrier = defaultPayloadConverter.fromPayload<Record<string, string>>(payload);
    if (!carrier || typeof carrier !== 'object') {
      return undefined;
    }
    return propagation.extract(context.active(), carrier);
  } catch {
    return undefined;
  }
}

/**
 * Headers that an outbound HTTP call made from the current context would
 * carry (e.g. `baggage: sd-routing-key=...`).
 *
 * Instrumented HTTP clients (e.g. @opentelemetry/instrumentation-undici for
 * fetch, or @opentelemetry/instrumentation-http) inject these automatically.
 * Application activities only need this for clients without instrumentation:
 * pass the result as request headers.
 */
export function outboundHttpHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};
  propagation.inject(context.active(), headers);
  return headers;
}
