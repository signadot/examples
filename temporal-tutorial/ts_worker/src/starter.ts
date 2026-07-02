/**
 * Local test client: starts a MoneyTransferWorkflow, optionally tagged with a
 * Signadot routing key placed in OTel Baggage (exactly what the Signadot
 * sidecars/ingress do to requests routed to a sandbox).
 *
 * Usage:
 *   node lib/starter.js                  # baseline (no routing key)
 *   node lib/starter.js <routing-key>    # routed to matching sandbox worker
 *
 * The Python py_client web UI works with this worker too: both SDKs store the
 * OTel context under the same `_tracer-data` header.
 */
import { Client, Connection } from '@temporalio/client';
import { context, propagation } from '@opentelemetry/api';
import { OpenTelemetryWorkflowClientInterceptor } from '@temporalio/interceptors-opentelemetry';
import { setupOpenTelemetry } from './signadot/otel';
import { ROUTING_KEY_BAGGAGE_KEY } from './signadot/tracer-headers';
import type { PaymentDetails } from './models';

async function main(): Promise<void> {
  setupOpenTelemetry();
  const routingKey = process.argv[2] ?? '';

  const connection = await Connection.connect({
    address: process.env.TEMPORAL_SERVER_URL ?? 'localhost:7233',
  });
  const client = new Client({
    connection,
    // Injects the active OTel context (trace context + baggage) into the
    // workflow headers under `_tracer-data`.
    interceptors: { workflow: [new OpenTelemetryWorkflowClientInterceptor()] },
  });

  let ctx = context.active();
  if (routingKey) {
    const bag = propagation.getBaggage(ctx) ?? propagation.createBaggage();
    ctx = propagation.setBaggage(ctx, bag.setEntry(ROUTING_KEY_BAGGAGE_KEY, { value: routingKey }));
  }

  const payment: PaymentDetails = {
    from_account: 'acc_001',
    to_account: 'acc_002',
    amount: '50.00',
    reference: 'ts-starter',
  };

  const result = await context.with(ctx, async () => {
    const handle = await client.workflow.start('MoneyTransferWorkflow', {
      taskQueue: process.env.TASK_QUEUE ?? 'money-transfer',
      workflowId: `money-transfer-${randomSuffix()}`,
      args: [payment],
    });
    console.log(`Started workflow ${handle.workflowId} (routing key: '${routingKey}')`);
    return await handle.result();
  });
  console.log(`Result: ${result}`);
}

function randomSuffix(): string {
  return Math.random().toString(36).slice(2, 10);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
