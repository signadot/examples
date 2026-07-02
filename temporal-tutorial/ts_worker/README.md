# Temporal Worker (TypeScript)

A sandbox-aware Temporal worker built with the Temporal **TypeScript SDK**. It implements the same Signadot routing-key isolation as the Python worker (`../temporal_worker`), adapted to the TypeScript SDK's deterministic workflow runtime.

## Code layout: platform vs. application

The code is split so that a platform team can own all Signadot-specific
machinery while application developers write ordinary Temporal code:

```
src/
├── signadot/                     # PLATFORM LAYER (owned by the platform team)
│   ├── worker.ts                 #   SandboxAwareWorker: wires everything below
│   ├── workflow-interceptors.ts  #   routing check inside the V8 isolate + header propagation
│   ├── activity-interceptor.ts   #   activity routing check + OTel baggage bridging
│   ├── routing.ts                #   routeserver client with cached routing rules
│   ├── tracer-headers.ts         #   isolate-safe helpers for the _tracer-data header
│   └── otel.ts                   #   OTel setup + header helpers (Node.js side)
├── worker.ts                     # APPLICATION: entry point (registers workflows/activities)
├── workflows.ts                  # APPLICATION: pure workflow logic
├── activities.ts                 # APPLICATION: pure activity logic
├── models.ts                     # APPLICATION: data models
└── starter.ts                    # dev/test client for starting workflows
```

Application code contains **no Signadot- or OpenTelemetry-specific logic**.
The only integration point is the entry point:

```typescript
// src/worker.ts
import { SandboxAwareWorker } from './signadot/worker';
import * as activities from './activities';

const worker = await SandboxAwareWorker.create({
  taskQueue,
  workflowsPath: require.resolve('./workflows'),
  activities,
});
await worker.run();
```

`SandboxAwareWorker` registers both interceptor layers, polls the routeserver,
and injects the platform's `signadotShouldProcess` local activity that backs
the workflow-level routing check — application developers never define or see
it. Activities that use an HTTP client without OTel instrumentation can ask
the platform layer for outbound headers explicitly (`outboundHttpHeaders()`
from `signadot/otel`).

## Why TypeScript needs a different design

The Python worker's interceptors can freely read worker memory and do I/O: its workflow interceptor reads the routeserver-backed routing cache directly. The TypeScript SDK is different: **workflow code (including workflow interceptors) runs inside a deterministic V8 isolate** with no network access, no Node.js APIs, and no access to the worker process's memory. A workflow interceptor cannot query the routeserver or read a cache the way the Python one does.

This example solves that with a two-layer design:

### 1. Workflow task routing (inside the V8 isolate)

`src/signadot/workflow-interceptors.ts` runs in the workflow isolate and:

- **Reads the routing key deterministically** from the `_tracer-data` header (the serialized OTel context written by the client) using a pure string parse — no OTel runtime in the isolate.
- **Delegates the routing decision to a local activity** (`signadotShouldProcess`). Local activities execute on the Node.js side of *this same worker*, with full I/O access to the routeserver-backed cache. The result is recorded as a marker in workflow history, so replay is deterministic: if the baseline worker later takes over a sandbox-started workflow (e.g. the sandbox was deleted), replay sees the recorded `true` and continues.
- **Throws a plain `Error` when the task isn't for this worker.** In the TypeScript SDK, an error that is not a `TemporalFailure` fails the *workflow task*, not the workflow. The server retries the task until a worker that matches the routing key polls it — the same polling-based distribution the Python worker uses. Commands from the failed task (including the local activity marker) are discarded, so the next worker re-runs its own check.
- **Propagates the `_tracer-data` header** onto every activity, local activity, child workflow, signal, and continue-as-new the workflow schedules, by copying the payload verbatim in an outbound interceptor. This is deliberately a pure string copy instead of the OTel SDK propagators: workflow isolates are reused across workflow runs (`reuseV8Context`), and keeping mutable OpenTelemetry runtime state out of the isolate keeps every run and replay identical.

### 2. Activity task routing + OTel Baggage bridging (Node.js side)

`SignadotActivityInboundInterceptor` (`src/signadot/activity-interceptor.ts`) runs on the Node.js side with no determinism constraints and does two things:

- **Routing check**: extracts the routing key from the activity headers and rejects tasks this worker shouldn't process (the failed attempt is retried per the activity retry policy until the right worker picks it up). Local activities are exempt: they always run on the worker that's executing the workflow task, which already passed the workflow-level check.
- **Baggage bridging**: restores the OTel context from the headers **around the activity execution**, so `sd-routing-key` is in OTel Baggage while your activity code runs. Any outbound HTTP call made from an activity carries `baggage: sd-routing-key=...` and gets routed to the right sandboxes downstream. (The SDKs do not do this by themselves; it is the same gap the Python worker closes — see `../temporal_worker/README.md`.) The worker logs the effective outbound headers per activity so this is easy to verify.

To have HTTP clients inject those headers automatically, run the OTel NodeSDK with `@opentelemetry/instrumentation-undici` (for `fetch`) or `@opentelemetry/instrumentation-http`; this example keeps the setup minimal (`src/signadot/otel.ts`).

## Cross-SDK compatibility

The Python, TypeScript, and Java Temporal SDKs' OpenTelemetry interceptors all store the context under the same `_tracer-data` header, as a JSON text map with W3C `traceparent`/`baggage` entries. Workflows started by the Python `py_client` are routed and processed correctly by this worker, and vice versa.

## Quick Start

### Local Development

1. Install dependencies and build:
   ```bash
   npm install
   npm run build
   ```

2. Set the environment (same variables as the Python worker):
   ```bash
   export TASK_QUEUE=money-transfer-ts
   export TEMPORAL_SERVER_URL=localhost:7233
   export ROUTES_API_ROUTE_SERVER_ADDR=http://localhost:7778
   export ROUTES_API_BASELINE_KIND=Deployment
   export ROUTES_API_BASELINE_NAMESPACE=temporal
   export ROUTES_API_BASELINE_NAME=temporal-worker-ts
   export ROUTES_API_REFRESH_INTERVAL_SECONDS=120
   # Only set on sandboxed workers (Signadot sets this automatically in-cluster):
   # export SIGNADOT_SANDBOX_NAME=my-sandbox
   ```

3. Run the worker:
   ```bash
   npm run worker
   ```

4. Start a test workflow:
   ```bash
   node lib/starter.js                    # baseline (no routing key)
   node lib/starter.js <routing-key>      # routed to the matching sandbox worker
   ```

### Docker

```bash
./build.sh
docker run temporal-money-transfer-ts:v1.0
```

### Kubernetes

```bash
./build.sh
kubectl apply -f ../k8s/ts-worker-deployment.yaml
```

Create a sandbox that forks the TypeScript worker:

```bash
signadot sandbox apply -f ../sandbox/ts-worker-sandbox.yaml --set cluster=<your-cluster>
```

## Environment Variables

| Variable | Description |
| --- | --- |
| `TASK_QUEUE` | Task queue name (e.g. `money-transfer-ts`) |
| `TEMPORAL_SERVER_URL` | Temporal server address |
| `SIGNADOT_SANDBOX_NAME` | Set on sandboxed workers; empty/unset means baseline |
| `ROUTES_API_ROUTE_SERVER_ADDR` | Signadot routeserver address |
| `ROUTES_API_BASELINE_KIND` | Baseline workload kind (e.g. `Deployment`) |
| `ROUTES_API_BASELINE_NAMESPACE` | Baseline workload namespace |
| `ROUTES_API_BASELINE_NAME` | Baseline workload name |
| `ROUTES_API_REFRESH_INTERVAL_SECONDS` | Routing rules cache refresh interval |
