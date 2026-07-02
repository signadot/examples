# Signadot Temporal Integration

This repository demonstrates how to integrate Temporal workflows with Signadot sandbox routing for multi-tenant applications.

## Tutorial Overview: Sandbox Integration with Temporal

This tutorial demonstrates how to enable the use of sandboxes with Temporal workflows and activities through an interceptor-based routing mechanism. Workers for the same task queue run both as the baseline deployment and inside Signadot sandboxes; interceptors make sure each task is processed by the worker version that matches the request's routing key.

### How It Works

1. **Client-Side Context Propagation**: The client uses the OpenTelemetry interceptor provided by the Temporal SDK (`TracingInterceptor` in Python, `OpenTelemetryWorkflowClientInterceptor` in TypeScript) to propagate the client's OTel Baggage — including the Signadot routing key (`sd-routing-key`) — into the workflow submission. The serialized context is stored under the `_tracer-data` key in the "headers" structure in Temporal's persistent storage. The header format is the same across the Python, TypeScript, and Java SDKs, so clients and workers can mix SDKs.

2. **Worker-Side Task Routing**: Custom worker interceptors read the routing key from the task headers and query the Signadot routeserver (with a periodically refreshed cache) to decide whether this worker should process the task:
   - **Sandbox workers** only process tasks whose routing key maps to their sandbox.
   - **Baseline workers** process everything else, including tasks with unknown/stale routing keys.

3. **Polling-Based Distribution**: When a worker rejects a task, the raised error fails only that workflow task / activity attempt, and the Temporal server retries it. Since all workers (baseline and sandboxed) keep polling the same task queue, the right worker eventually processes the task. There are configuration options (retries, backoff, etc.) that can make this more efficient; those optimizations are outside the scope of this tutorial.

4. **Routing Key Propagation into Activities (OTel Baggage bridging)**: Accepting/rejecting tasks is not enough — activity code frequently makes **outbound HTTP calls to other services**, and those calls must carry the routing key for downstream sandbox routing to keep working. The workers bridge the routing key from the task headers into OTel Baggage, scoped to each activity execution, so outbound HTTP requests made from activities automatically carry `baggage: sd-routing-key=...`. (The SDKs' tracing interceptors do not do this by themselves for activities — see the worker READMEs for details, including the Java equivalent.)

This approach ensures that workflows and activities are executed in the appropriate sandbox environment — and that calls leaving the workers stay on the right route — while maintaining the reliability and durability guarantees that Temporal provides.

### Platform vs. application code

Both workers separate ownership the way a real organization would:

- **Platform layer** (`temporal_worker/signadot/` in Python, `ts_worker/src/signadot/` in TypeScript): interceptors, routeserver integration, and OTel context/baggage propagation. Implemented once by the platform team.
- **Application code** (workflows, activities, models, entry point): ordinary Temporal code with **no Signadot- or OpenTelemetry-specific logic**. The only integration point is constructing the platform's `SandboxAwareWorker` in the entry point and handing it your workflows and activities.

## Components

This project consists of three main components:

### 1. **py_client** - FastAPI Web Interface
A FastAPI-based web application that provides a user interface for starting Temporal workflows with automatic OpenTelemetry context propagation. It works with both the Python and TypeScript workers.

**📁 [py_client/README.md](py_client/README.md)** - Detailed documentation and setup instructions

### 2. **temporal_worker** - SandboxAware Temporal Worker (Python)
A Temporal worker that automatically handles Signadot sandbox routing and context propagation, allowing developers to focus on domain-specific workflows and activities.

**📁 [temporal_worker/README.md](temporal_worker/README.md)** - Detailed documentation and setup instructions

### 3. **ts_worker** - SandboxAware Temporal Worker (TypeScript)
The same routing pattern built with the Temporal TypeScript SDK. The TypeScript SDK runs workflow code in a deterministic V8 isolate (no I/O, no worker memory access), so the workflow-side routing check is implemented differently: a deterministic header parse plus a local activity that consults the routeserver from the Node.js side.

**📁 [ts_worker/README.md](ts_worker/README.md)** - Detailed documentation, including how the V8 isolate constraints shape the design

## Quick Start

### Prerequisites

1. **Install Signadot Components:**
   ```bash
   # Install the Signadot operator in your Kubernetes cluster
   # Follow the official documentation: https://www.signadot.com/docs/installation/signadot-operator
   
   # Install the Signadot CLI
   # Option 1: Via Homebrew (recommended for macOS/Linux)
   brew tap signadot/tap
   brew install signadot-cli
   
   # Option 2: Via script
   curl -sSLf https://raw.githubusercontent.com/signadot/cli/main/scripts/install.sh | sh
   
   # Option 3: Download from releases
   # Visit: https://github.com/signadot/cli/releases
   ```

2. **Deploy Temporal Server:**
   ```bash
   # Create the temporal namespace
   kubectl create namespace temporal
   
   # Apply all Temporal components
   kubectl apply -f k8s/temporal/
   ```

3. **Connect to Remote Services (if applicable):**
   ```bash
   # If your client and workers are running locally but Temporal is deployed remotely
   signadot local connect
   ```

### Running the Application

1. **Start a Temporal worker** (Python, TypeScript, or both — they use separate task queues):
   ```bash
   # Python worker (task queue: money-transfer)
   cd temporal_worker
   python main.py

   # TypeScript worker (task queue: money-transfer-ts)
   cd ts_worker
   npm install && npm run build && npm run worker
   ```

2. **Start the web interface:**
   ```bash
   cd py_client
   uvicorn main:app --reload --host 0.0.0.0 --port 8080
   ```
   Set `TASK_QUEUE=money-transfer-ts` to submit workflows to the TypeScript worker instead of the Python one.

3. **Access the web UI:**
   Open your browser to `http://localhost:8080`

### Testing with sandboxes

Create a sandbox that forks a worker deployment, then send requests with the sandbox's routing key:

```bash
signadot sandbox apply -f sandbox/worker-sandbox.yaml --set cluster=<your-cluster>     # Python worker
signadot sandbox apply -f sandbox/ts-worker-sandbox.yaml --set cluster=<your-cluster>  # TypeScript worker
```

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌──────────────────────┐
│   py_client     │    │   Temporal      │    │  temporal_worker(py) │
│   (Web UI)      │───▶│   Server        │◀───│  ts_worker (ts)      │
└─────────────────┘    └─────────────────┘    │  (baseline+sandboxes)│
                                              └──────────────────────┘
```

The client submits workflows for execution to the Temporal server, and Temporal workers poll the server for tasks. Baseline and sandboxed workers poll the same task queue; the interceptors ensure each task lands on the right version.

See the individual README files for detailed development instructions.
