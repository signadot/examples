# Temporal Worker Sandbox Integration Example

This repository demonstrates integrating Temporal workflows with Signadot sandbox routing, allowing tests of changed worker versions against a shared task queue with automatic request isolation.

For the guided step-by-step walkthrough, see the [full tutorial](https://www.signadot.com/docs/tutorials/testing-temporal-workers).

## Quick Start

### Prerequisites

- A Minikube cluster with the [Signadot Operator installed](https://www.signadot.com/docs/getting-started/installation)
- The [Signadot CLI](https://www.signadot.com/docs/reference/cli) installed and authenticated
- `kubectl` pointing at the cluster
- Docker and the `minikube` CLI

Clone the examples repository, then build and deploy the shared web client and Temporal stack:

```bash
git clone https://github.com/signadot/examples.git
cd examples/temporal-tutorial

docker build -t temporal-py-client-ui:v1.0 py_client
minikube image load temporal-py-client-ui:v1.0

kubectl create namespace temporal
kubectl apply -n temporal -f k8s/temporal/
```

Choose one worker language and run its commands.

<details>
<summary>Python</summary>

```bash
docker build -t temporal-money-transfer:v1.0 temporal_worker
minikube image load temporal-money-transfer:v1.0

kubectl apply -n temporal -f k8s/worker-deployment.yaml
kubectl apply -n temporal -f k8s/temporal-py-client-ui-deployment.yaml

docker build -t temporal-money-transfer:sandbox temporal_worker
minikube image load temporal-money-transfer:sandbox

signadot sandbox apply -f sandbox/worker-sandbox.yaml \
  --set cluster=<your-cluster-name> \
  --set image=temporal-money-transfer:sandbox
```

</details>

<details>
<summary>TypeScript</summary>

```bash
docker build -t temporal-money-transfer-ts:v1.0 ts_worker
minikube image load temporal-money-transfer-ts:v1.0

kubectl apply -n temporal -f k8s/ts-worker-deployment.yaml
kubectl apply -n temporal -f k8s/temporal-py-client-ui-deployment.yaml
kubectl set env -n temporal deployment/temporal-py-client-ui TASK_QUEUE=money-transfer-ts

docker build -t temporal-money-transfer-ts:sandbox ts_worker
minikube image load temporal-money-transfer-ts:sandbox

signadot sandbox apply -f sandbox/ts-worker-sandbox.yaml \
  --set cluster=<your-cluster-name> \
  --set image=temporal-money-transfer-ts:sandbox
```

</details>

<details>
<summary>Go</summary>

```bash
docker build -t temporal-money-transfer-go:v1.0 go_worker
minikube image load temporal-money-transfer-go:v1.0

kubectl apply -n temporal -f k8s/go-worker-deployment.yaml
kubectl apply -n temporal -f k8s/temporal-py-client-ui-deployment.yaml
kubectl set env -n temporal deployment/temporal-py-client-ui TASK_QUEUE=money-transfer-go

docker build -t temporal-money-transfer-go:sandbox go_worker
minikube image load temporal-money-transfer-go:sandbox

signadot sandbox apply -f sandbox/go-worker-sandbox.yaml \
  --set cluster=<your-cluster-name> \
  --set image=temporal-money-transfer-go:sandbox
```

</details>

<details>
<summary>Java</summary>

```bash
docker build -t temporal-money-transfer-java:v1.0 java_worker
minikube image load temporal-money-transfer-java:v1.0

kubectl apply -n temporal -f k8s/java-worker-deployment.yaml
kubectl apply -n temporal -f k8s/temporal-py-client-ui-deployment.yaml
kubectl set env -n temporal deployment/temporal-py-client-ui TASK_QUEUE=money-transfer-java

docker build -t temporal-money-transfer-java:sandbox java_worker
minikube image load temporal-money-transfer-java:sandbox

signadot sandbox apply -f sandbox/java-worker-sandbox.yaml \
  --set cluster=<your-cluster-name> \
  --set image=temporal-money-transfer-java:sandbox
```

</details>

Wait for the baseline and sandbox workloads to become ready:

```bash
kubectl get pods -n temporal -w
```

The `signadot sandbox apply` output includes a preview URL. Open it and submit a workflow to test the sandboxed worker. For the complete tagged and untagged verification, worker-log checks, implementation details, and tradeoffs, follow the [full tutorial](https://www.signadot.com/docs/tutorials/testing-temporal-workers).

## How It Works

1. **Client propagation**: The web client stamps the Signadot routing key into OpenTelemetry baggage, propagated to the Temporal server via `_tracer-data` task headers.

2. **Workflow routing check**: Interceptors read the routing key and query the Signadot Routes API; workflows with mismatched keys are rejected, triggering server retries.

3. **Deterministic retry**: Both baseline and sandboxed workers poll the same task queue. Temporal retries rejected tasks until the right worker (whose routing key matches) accepts it.

4. **Activity propagation**: Activity interceptors bridge the routing key from task headers into OpenTelemetry baggage for the duration of execution, so outbound HTTP calls automatically carry the routing context downstream.

For the detailed mechanism and code walkthroughs, see the [docs tutorial](https://www.signadot.com/docs/tutorials/testing-temporal-workers).

## Components

| Component | Purpose | Docs |
|-----------|---------|------|
| **py_client** | FastAPI web UI; starts workflows with OTel propagation, works with every worker | [py_client/README.md](py_client/README.md) |
| **temporal_worker** (Python) | Worker with sandbox routing; queue `money-transfer` | [temporal_worker/README.md](temporal_worker/README.md) |
| **ts_worker** (TypeScript) | Worker with sandbox routing; queue `money-transfer-ts` | [ts_worker/README.md](ts_worker/README.md) |
| **go_worker** (Go) | Worker with sandbox routing; queue `money-transfer-go` | [go_worker/README.md](go_worker/README.md) |
| **java_worker** (Java) | Worker with sandbox routing; queue `money-transfer-java` | [java_worker/README.md](java_worker/README.md) |

## Platform vs. Application Code

This example separates concerns:

- **Platform layer** (`temporal_worker/signadot/`, `ts_worker/src/signadot/`, `go_worker/signadot/`, `java_worker/src/.../signadot/`): Interceptors, routeserver integration, OTel baggage bridging. Implemented once by the platform team.
- **Application code** (workflows, activities, models): Ordinary Temporal code with no Signadot- or OpenTelemetry-specific logic. Integration point is the `SandboxAwareWorker` constructor in the entry point.

## Cleanup

Delete the sandbox you created:

- Python: `signadot sandbox delete temporal-worker-sandbox`
- TypeScript: `signadot sandbox delete temporal-worker-ts-sandbox`
- Go: `signadot sandbox delete temporal-worker-go-sandbox`
- Java: `signadot sandbox delete temporal-worker-java-sandbox`

Then remove the demo namespace:

```bash
kubectl delete namespace temporal
```

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌──────────────────────┐
│   py_client     │    │   Temporal      │    │  temporal_worker (py)│
│   (Web UI)      │───>│   Server        │<───│  ts_worker (ts)      │
└─────────────────┘    └─────────────────┘    │  go_worker (go)      │
                                              │  java_worker (java)  │
                                              │ (baseline+sandboxes) │
                                              └──────────────────────┘
```

The client submits workflows to the Temporal server; workers poll the server for tasks. Baseline and sandboxed workers poll the same queue; interceptors route each task to the correct version.
