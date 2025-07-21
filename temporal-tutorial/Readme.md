# Signadot Temporal Integration

This repository demonstrates how to integrate Temporal workflows with Signadot sandbox routing for multi-tenant applications.

## Tutorial Overview: Sandbox Integration with Temporal

This tutorial demonstrates how to enable the use of sandboxes with Temporal workflows and activities through a sophisticated interceptor-based routing mechanism.

### How It Works

1. **Client-Side Context Propagation**: The client uses the `TracingInterceptor` provided by the Temporal Python SDK to propagate client-side baggage into the workflow submission task. This baggage gets stored within the "headers" structure in Temporal's persistent storage.

2. **Worker-Side Routing**: On the worker side, we leverage the `TracingInterceptor` to propagate baggage (which contains the Signadot routing key) and implement custom interceptors to intercept calls to execute workflows and activities.

3. **Task Routing Logic**: In these custom interceptors, we query the routeserver to determine if this worker should process the task or not, and accordingly skip or process the task.

4. **Polling-Based Distribution**: Since all workers keep polling the server for tasks, eventually the right worker will process the task. While there are several configuration options that could make this more efficient (related to retries, backoff, etc.), those optimizations are outside the scope of this tutorial.

This approach ensures that workflows and activities are executed in the appropriate sandbox environment while maintaining the reliability and durability guarantees that Temporal provides.

## Components

This project consists of two main components:

### 1. **py_client** - FastAPI Web Interface
A FastAPI-based web application that provides a user interface for starting Temporal workflows with automatic OpenTelemetry context propagation.

**📁 [py_client/README.md](py_client/README.md)** - Detailed documentation and setup instructions

### 2. **temporal_worker** - SandboxAware Temporal Worker
A Temporal worker that automatically handles Signadot sandbox routing and context propagation, allowing developers to focus on domain-specific workflows and activities.

**📁 [temporal_worker/README.md](temporal_worker/README.md)** - Detailed documentation and setup instructions

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

1. **Start the Temporal worker:**
   ```bash
   cd temporal_worker
   python main.py
   ```

2. **Start the web interface:**
   ```bash
   cd py_client
   uvicorn main:app --reload --host 0.0.0.0 --port 8080
   ```

3. **Access the web UI:**
   Open your browser to `http://localhost:8080`

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   py_client     │    │   Temporal      │    │  temporal_worker│
│   (Web UI)      │───▶│   Server        │◀───│   (Worker)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

The client submits workflows for execution to the Temporal server, and Temporal workers poll the server for tasks.

See the individual README files for detailed development instructions.