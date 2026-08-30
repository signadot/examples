# Temporal Worker - Java

A Temporal worker implementation in Java demonstrating sandbox routing via Signadot. Mirrors the Python and TypeScript reference implementations.

## Architecture

The worker is structured into two layers:

**Application Layer** (`app/` package)
- `MoneyTransferWorkflow`: Workflow orchestrating a two-step money transfer
- `BankingActivities`: Activities for withdraw and deposit operations
- Workflows and activities contain zero Signadot or OpenTelemetry logic

**Platform Layer** (`signadot/` package)
- `RoutesClient`: Polls the Signadot routeserver for routing rules (every 5 seconds by default)
- `WorkflowRoutingInterceptor`: Workflow-level routing check. Since workflow code must not read mutable process state, the decision runs as a local activity (`signadotShouldProcess`) whose result is recorded in history, keeping replays deterministic — the same pattern as the Go and TypeScript workers. Unmatched routing keys are rejected with a RuntimeException, which fails only the workflow task (server retries)
- `ActivityRoutingInterceptor`: Activity-level routing check; rejects with retryable ApplicationFailure carrying a 1s next-retry delay, and restores the OTel context (trace + baggage) around the activity so outbound calls made with an OTel-instrumented HTTP client carry the routing key downstream
- `SignadotRoutingActivities`: The platform-provided local activity backing the workflow routing check
- `SandboxAwareWorkerFactory`: Wires all platform components with the Temporal SDK

## Routing Key Isolation

The routing key (`sd-routing-key`) arrives in OTel baggage serialized in the `_tracer-data` task header (same wire format across SDKs).

- Sandbox workers only process tasks whose routing keys route to their sandbox
- Baseline workers process everything else (fallback for unknown/stale keys)
- Rejection semantics ensure tasks are retried by the right worker

## Running Locally

Prerequisites: Java 21, Maven 3.9+

```bash
mvn -q -DskipTests package
java -cp target/app.jar com.signadot.temporaldemo.Main
```

Environment variables:
- `TASK_QUEUE` (default: money-transfer-java)
- `TEMPORAL_SERVER_URL` (required)
- `ROUTES_API_ROUTE_SERVER_ADDR` (required)
- `ROUTES_API_BASELINE_KIND` (required)
- `ROUTES_API_BASELINE_NAMESPACE` (required)
- `ROUTES_API_BASELINE_NAME` (required)
- `ROUTES_API_REFRESH_INTERVAL_SECONDS` (default: 5)
- `SIGNADOT_SANDBOX_NAME` (optional; set when running sandboxed)

## Deployment

See ../k8s/java-worker-deployment.yaml and ../sandbox/java-worker-sandbox.yaml.

For full tutorial context: https://www.signadot.com/docs/tutorials/testing-temporal-workers
