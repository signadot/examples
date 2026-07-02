/**
 * Activity inbound interceptor implementing Signadot routing-key isolation.
 * Platform-owned: wired up by SandboxAwareWorker; application activities never
 * see it.
 *
 * Unlike workflow interceptors, activity interceptors run on the Node.js side
 * of the worker (no determinism constraints), so this can consult the
 * routeserver-backed cache directly. It does two things:
 *
 * 1. Rejects activity tasks whose routing key this worker should not process.
 *    The failed attempt is retried per the activity retry policy until the
 *    right worker picks it up.
 * 2. Restores the OTel context (including the sd-routing-key baggage) from the
 *    task headers around the activity execution, so outbound HTTP calls made
 *    by application activities automatically carry the routing key and get
 *    routed to the right sandboxes downstream. This is the piece the SDKs do
 *    not do by themselves.
 */
import { context as otelContext } from '@opentelemetry/api';
import type { ActivityInboundCallsInterceptor, ActivityExecuteInput, Next } from '@temporalio/worker';
import type { Context as ActivityContext } from '@temporalio/activity';
import { routingKeyFromHeaders } from './tracer-headers';
import { contextFromHeaders, outboundHttpHeaders } from './otel';
import { RoutesAPIClient } from './routing';

export class SignadotActivityInboundInterceptor implements ActivityInboundCallsInterceptor {
  constructor(
    private readonly ctx: ActivityContext,
    private readonly routesClient: RoutesAPIClient,
    private readonly workerIdent: string
  ) {}

  async execute(input: ActivityExecuteInput, next: Next<ActivityInboundCallsInterceptor, 'execute'>): Promise<unknown> {
    // Local activities always execute on the worker that is processing the
    // workflow task, and that worker already passed the workflow-level routing
    // check -- this also covers the `signadotShouldProcess` check itself.
    const isLocal = this.ctx.info.isLocal;
    if (!isLocal) {
      const routingKey = routingKeyFromHeaders(input.headers);
      if (!this.routesClient.shouldProcess(routingKey)) {
        // Fails only this attempt; the server retries the activity (per its
        // retry policy) until a worker that matches the routing key picks it up.
        throw new Error(
          `Activity/Worker cannot handle routing key: '${routingKey}' - Worker: ${this.workerIdent}`
        );
      }
      console.log(
        `[Worker:${this.workerIdent}] Activity: ${this.ctx.info.activityType}: Processing task with routing key '${routingKey}'`
      );
    }

    // Bridge the OTel context (trace context + baggage) from the task headers
    // around the activity execution.
    const headerContext = contextFromHeaders(input.headers);
    if (headerContext === undefined) {
      return next(input);
    }
    return otelContext.with(headerContext, () => {
      if (!isLocal) {
        console.log(
          `[Worker:${this.workerIdent}] Activity: ${this.ctx.info.activityType}: outbound HTTP calls will carry: ${JSON.stringify(outboundHttpHeaders())}`
        );
      }
      return next(input);
    });
  }
}
