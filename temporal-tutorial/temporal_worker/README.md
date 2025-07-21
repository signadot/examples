# Temporal Worker

A Temporal worker that automatically handles Signadot sandbox routing and context propagation.

## Quick Start

### Local Development

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Edit the `.env` file with your configuration

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
- **Graceful Shutdown**: Proper signal handling and cleanup
- **Background Cache Updates**: Automatic routing cache refresh

## Environment Variables

- **Local Development**: Use `.env` file with `python -m dotenv`
- **Production**: Set via Kubernetes manifests (see `k8s/worker-deployment.yaml`)

See `.env` for all required environment variables. 