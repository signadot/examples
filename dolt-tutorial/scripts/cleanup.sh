#!/bin/bash
# cleanup.sh
# Removes the sandbox, Resource Plugin, location service, and Dolt server.
#
# Usage:
#   ./scripts/cleanup.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Step 1: Delete sandbox (if it exists) ==="
signadot sandbox delete dolt-sandbox-demo 2>/dev/null \
  && echo "Sandbox deleted." \
  || echo "No sandbox to delete."
echo ""

echo "=== Step 2: Delete Resource Plugin ==="
signadot resourceplugin delete dolt-branch 2>/dev/null \
  && echo "Resource Plugin deleted." \
  || echo "No Resource Plugin to delete."
echo ""

echo "=== Step 3: Remove location service ==="
kubectl delete -f "${ROOT_DIR}/k8s/location-service.yaml" --ignore-not-found
echo ""

echo "=== Step 4: Remove Dolt resources ==="
kubectl delete -f "${ROOT_DIR}/k8s/dolt-deployment.yaml" --ignore-not-found
kubectl delete -f "${ROOT_DIR}/k8s/dolt-service.yaml" --ignore-not-found
kubectl delete -f "${ROOT_DIR}/k8s/dolt-init-configmap.yaml" --ignore-not-found
kubectl delete secret dolt-credentials --ignore-not-found
echo ""

echo "=== Cleanup complete ==="