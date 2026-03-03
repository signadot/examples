#!/bin/bash
# deploy.sh
# Deploys Dolt, builds and deploys the location service, and registers
# the Signadot Resource Plugin.
#
# Prerequisites:
#   - kubectl configured with access to your cluster
#   - Signadot CLI installed
#   - Docker available (for building the location service image)
#
# Usage:
#   ./scripts/deploy.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Step 1: Authenticate Signadot CLI ==="
if signadot auth status 2>/dev/null | grep -q "Authenticated"; then
  echo "Signadot CLI is already authenticated."
else
  echo "The Signadot CLI is not authenticated."
  echo "Generate an API key at: https://app.signadot.com/settings/apikeys"
  echo ""
  read -s -p "Paste your Signadot API key: " SIGNADOT_API_KEY
  echo ""
  if [ -z "${SIGNADOT_API_KEY}" ]; then
    echo "Error: API key cannot be empty."
    exit 1
  fi
  signadot auth login --with-api-key "${SIGNADOT_API_KEY}"
  echo "Signadot CLI authenticated."
fi
echo ""

echo "=== Step 2: Create Dolt credentials Secret ==="
read -s -p "Enter a password for the Dolt root user: " DOLT_PASSWORD
echo ""
if [ -z "${DOLT_PASSWORD}" ]; then
  echo "Error: password cannot be empty."
  exit 1
fi
kubectl create secret generic dolt-credentials \
  --from-literal=username=root \
  --from-literal=password="${DOLT_PASSWORD}" \
  --dry-run=client -o yaml | kubectl apply -f -
echo "Secret 'dolt-credentials' created."
echo ""

echo "=== Step 3: Build the location service image ==="
# For minikube: eval $(minikube docker-env) before running this script
# so the image is built inside minikube's Docker daemon.
docker build -t location-service:latest "${ROOT_DIR}/app"
echo "Image 'location-service:latest' built."
echo ""

echo "=== Step 4: Deploy Dolt SQL server ==="
kubectl apply -f "${ROOT_DIR}/k8s/dolt-init-configmap.yaml"
kubectl apply -f "${ROOT_DIR}/k8s/dolt-deployment.yaml"
kubectl apply -f "${ROOT_DIR}/k8s/dolt-service.yaml"
echo ""

echo "=== Step 5: Wait for Dolt pod to be ready ==="
kubectl rollout status deployment/dolt-db --timeout=180s
echo ""

echo "=== Step 6: Verify Dolt seed data ==="
DOLT_POD=$(kubectl get pod -l app=dolt-db -o jsonpath='{.items[0].metadata.name}')
echo "Dolt pod: ${DOLT_POD}"
kubectl exec "${DOLT_POD}" -c dolt -- \
  bash -c "cd /var/lib/dolt/location && dolt sql -q 'SELECT * FROM locations;'"
echo ""

echo "=== Step 7: Deploy location service ==="
kubectl apply -f "${ROOT_DIR}/k8s/location-service.yaml"
echo ""

echo "=== Step 8: Wait for location service ==="
kubectl rollout status deployment/location-service --timeout=120s
echo ""

echo "=== Step 9: Apply Signadot Resource Plugin ==="
signadot resourceplugin apply -f "${ROOT_DIR}/signadot/dolt-branch-plugin.yaml"
echo ""

echo "=== Deployment complete ==="
echo "Create sandboxes with:"
echo "  signadot sandbox apply -f signadot/sandbox.yaml --set cluster=<YOUR_CLUSTER> --set image=location-service:v2"