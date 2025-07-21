# Temporal Python Client UI

A simplified FastAPI-based web interface for starting Temporal workflows with OpenTelemetry context propagation.

## Quick Start

### Local Development

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the application:
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8080
   ```

3. Open your browser to `http://localhost:8080`

### Docker

1. Build the image:
   ```bash
   ./build.sh
   ```

2. Run the container:
   ```bash
   docker run -p 8080:8080 temporal-py-client-ui:v1.0
   ```

### Kubernetes

1. Build and deploy:
   ```bash
   ./build.sh
   kubectl apply -f ../k8s/temporal-py-client-ui-deployment.yaml
   ```

## Features

- **FastAPI Web Server**: Clean, modern web interface
- **Temporal Integration**: Direct workflow execution with proper context propagation
- **OpenTelemetry Support**: Automatic baggage propagation for routing
- **Baggage Display**: Shows all received baggage headers in the UI

## Environment Variables

- `TEMPORAL_SERVER_URL`: Temporal server address (default: `temporal.temporal:7233`)
- `TASK_QUEUE`: Task queue name (default: `money-transfer`)

## API Endpoints

- `GET /`: Web interface for starting workflows
- `POST /api/start-workflow`: API endpoint for workflow execution 