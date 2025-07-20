# Signadot Temporal Integration

This repository demonstrates how to integrate Temporal workflows with Signadot sandbox routing for multi-tenant applications.

## Overview

This project consists of two main components:

### 1. **py_client** - FastAPI Web Interface
A FastAPI-based web application that provides a user interface for starting Temporal workflows with automatic OpenTelemetry context propagation.

**📁 [py_client/README.md](py_client/README.md)** - Detailed documentation and setup instructions

### 2. **temporal_worker** - SandboxAware Temporal Worker
A Temporal worker that automatically handles Signadot sandbox routing and context propagation, allowing developers to focus on domain-specific workflows and activities.

**📁 [temporal_worker/README.md](temporal_worker/README.md)** - Detailed documentation and setup instructions

## Quick Start

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
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   py_client     │    │  temporal_worker │    │   Temporal      │
│   (Web UI)      │───▶│   (Worker)       │───▶│   Server        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Kubernetes Deployment

The repository includes Kubernetes deployment configurations in the `k8s/` directory.

## Signadot Integration

This project demonstrates how to:
- Route workflows to specific sandboxes based on routing keys
- Propagate OpenTelemetry context through the entire workflow execution
- Handle both baseline and sandbox worker deployments

See the individual README files for detailed development instructions.