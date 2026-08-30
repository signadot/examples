# Temporal Worker (Go)

A Go port of the Temporal worker with Signadot sandbox routing. This worker executes a money-transfer workflow with withdraw and deposit activities, automatically routing tasks to the correct sandbox based on the Signadot routing key.

## Key Architecture

The worker enforces deterministic replay semantics while supporting sandbox routing:

- **Workflow interceptor**: Since Go workflow code is deterministic and cannot perform I/O, the routing decision is delegated to a **local activity** (`signadotShouldProcess`). Its recorded result in the workflow history ensures replays are deterministic: once a worker accepts a workflow, later replays see the recorded decision and proceed without re-querying the routeserver.

- **Activity interceptor**: Non-local activities consult the routing cache directly; a wrong-worker rejection is a retryable failure with a ~1s next-retry delay, so the server quickly redelivers the task until the matching worker claims it. (Note: for *workflow* tasks the Go SDK reports a failure only on the first rejected attempt; later attempts on the wrong worker wait out the workflow task timeout, so sandbox handoff of a workflow task can take up to that timeout.) Additionally, the OTel context from task headers is restored around activity execution, so outbound calls made with an OTel-instrumented HTTP client (e.g. `otelhttp`) automatically carry the `sd-routing-key` baggage and route correctly downstream.

- **Application code**: Pure domain logic (workflows and activities) contains zero Signadot or OTel code. The platform layer in the `signadot` package handles all routing, caching, and context propagation.

## Running

The addresses below assume the Temporal server and Signadot routeserver are reachable on localhost — when they run in a cluster, use [`signadot local connect`](https://www.signadot.com/docs/reference/cli/local) to make them reachable first. Set environment variables and run:

```bash
export TASK_QUEUE="money-transfer-go"
export TEMPORAL_SERVER_URL="localhost:7233"
export ROUTES_API_ROUTE_SERVER_ADDR="http://localhost:7778"
export ROUTES_API_BASELINE_KIND="Deployment"
export ROUTES_API_BASELINE_NAMESPACE="temporal"
export ROUTES_API_BASELINE_NAME="temporal-worker-go"
# Optional: set sandbox name if running in a sandbox
# export SIGNADOT_SANDBOX_NAME="temporal-worker-go-sandbox"

go run main.go
```

## Layout

- `main.go`: Entry point constructing the sandbox-aware worker
- `signadot/`: Platform layer (routing.go, interceptors.go, worker.go)
- `app/`: Application domain code (models.go, workflows.go, activities.go)
- `Dockerfile`: Multi-stage Alpine build with distroless runtime

## Reference

See the full tutorial at https://www.signadot.com/docs/tutorials/testing-temporal-workers
