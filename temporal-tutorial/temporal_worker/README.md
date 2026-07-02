# Temporal Worker

A Temporal worker that automatically handles Signadot sandbox routing and context propagation.

## Code layout: platform vs. application

The code is split so that a platform team can own all Signadot-specific
machinery while application developers write ordinary Temporal code:

```
temporal_worker/
├── signadot/              # PLATFORM LAYER (owned by the platform team)
│   ├── worker.py          #   SandboxAwareWorker: wires everything below
│   ├── interceptors.py    #   routing-key task selection + OTel baggage bridging
│   └── routing.py         #   routeserver client with cached routing rules
├── main.py                # APPLICATION: entry point (registers workflows/activities)
├── workflows.py           # APPLICATION: pure workflow logic
├── activities.py          # APPLICATION: pure activity logic
└── models.py              # APPLICATION: data models
```

Application code contains **no Signadot- or OpenTelemetry-specific logic**.
The only integration point is the entry point:

```python
# main.py
from signadot import SandboxAwareWorker

worker = SandboxAwareWorker(
    task_queue=task_queue,
    workflows=[MoneyTransferWorkflow],
    activities=[banking_activities.withdraw, banking_activities.deposit],
)
await worker.start()
```

`SandboxAwareWorker` registers the interceptors, polls the routeserver, and
instruments aiohttp so outbound HTTP calls from activities carry the routing
key automatically. Activities that use an HTTP client without OTel
instrumentation can ask the platform layer for the headers explicitly:
`from signadot import outbound_http_headers`.

## Quick Start

### Local Development

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create your configuration:
   ```bash
   cp .env.example .env   # then adjust for your environment
   ```

3. Run the worker:
   ```bash
   python -m dotenv -f .env -- python main.py
   ```

### Docker

1. Build the image:
   ```bash
   ./build.sh
   ```

2. Run the container:
   ```bash
   docker run temporal-money-transfer:v1.0
   ```

### Kubernetes

1. Build and deploy:
   ```bash
   ./build.sh
   kubectl apply -f ../k8s/worker-deployment.yaml
   ```

## Features

- **SandboxAware Worker**: Automatically handles Signadot sandbox routing
- **OpenTelemetry Integration**: Context propagation and tracing
- **Baggage Bridging in Activities**: Outbound HTTP calls from activities carry the routing key
- **Graceful Shutdown**: Proper signal handling and cleanup
- **Background Cache Updates**: Automatic routing cache refresh

## Routing key propagation into activities (OTel Baggage bridging)

Accepting/rejecting tasks by routing key is only half the story: code inside an
activity often calls **other services over HTTP**, and those requests must also
carry the routing key so Signadot can route them to the right sandboxes
downstream.

The Temporal SDK's `TracingInterceptor` attaches the OTel context from the task
headers around **workflow** execution, but for **activities** it only uses that
context to parent the activity span — the baggage (which carries
`sd-routing-key`) is *not* attached while your activity code runs. Without
extra work, an outbound HTTP call made from an activity carries `traceparent`
but no `baggage`, and downstream sandbox routing silently breaks.

`SelectiveTaskInterceptor` (see `signadot/interceptors.py`) closes that gap:
after the routing check passes, it extracts the baggage from the task headers
and attaches it to the current OTel context **scoped to the activity
execution**:

```python
# signadot/interceptors.py (activity interceptor, simplified)
header_context = context_from_headers(input.headers)  # propagator-based extract
...
context = otel_context.get_current()
for key, value in baggage.get_all(header_context).items():
    context = baggage.set_baggage(key, value, context=context)
token = otel_context.attach(context)
try:
    return await self.next.execute_activity(input)
finally:
    otel_context.detach(token)
```

With that in place, any instrumented HTTP client (this worker instruments
aiohttp via `opentelemetry-instrumentation-aiohttp-client`; use the matching
package for `requests`/`httpx`) automatically injects
`baggage: sd-routing-key=...` on outbound requests made from activities. For
uninstrumented clients, inject manually with
`from signadot import outbound_http_headers` and pass the result as request
headers. The worker logs the effective outbound headers per activity so this
is easy to verify.

### Doing the same in Java

The Java SDK has the same behavior: the OpenTracing/OpenTelemetry module
restores the span context for activities, but Baggage is not made current
during activity execution. Bridge it in an `ActivityInboundCallsInterceptor`,
scoped to the activity call:

```java
public class SelectiveActivityInterceptor extends ActivityInboundCallsInterceptorBase {
    @Override
    public ActivityOutput execute(ActivityInput input) {
        String routingKey = routingKeyFromHeaders(input.getHeader()); // read sd-routing-key baggage
        // ... routing check (reject if this worker shouldn't process it) ...
        Baggage baggage = Baggage.current().toBuilder()
            .put("sd-routing-key", routingKey)
            .build();
        try (Scope ignored = baggage.makeCurrent()) {
            // Outbound HTTP calls made by the activity now carry
            // `baggage: sd-routing-key=...` via the W3CBaggagePropagator.
            return super.execute(input);
        }
    }
}
```

## Environment Variables

- **Local Development**: Use `.env` file with `python -m dotenv`
- **Production**: Set via Kubernetes manifests (see `k8s/worker-deployment.yaml`)

See `.env.example` for all required environment variables.
