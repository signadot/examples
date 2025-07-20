#!/bin/bash

# Build script for the simplified temporal_worker structure

set -e

echo "Building temporal-money-transfer Docker image..."

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running. Please start Docker and try again."
    exit 1
fi

# Build the Docker image
echo "Building Docker image..."
docker build -t temporal-money-transfer:v1.0 .

# Check if build was successful
if [ $? -eq 0 ]; then
    echo "✅ Docker image built successfully: temporal-money-transfer:v1.0"
    echo ""
    echo "To run locally:"
    echo "  docker run temporal-money-transfer:v1.0"
    echo ""
    echo "To deploy to Kubernetes:"
    echo "  kubectl apply -f ../k8s/worker-deployment.yaml"
    echo ""
    echo "To run with dotenv:"
    echo "  python -m dotenv run -- python main.py"
else
    echo "❌ Docker build failed"
    exit 1
fi