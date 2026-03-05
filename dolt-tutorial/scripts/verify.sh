#!/bin/bash
# verify.sh
# Verifies the Dolt deployment, location service, and sandbox status.
#
# Usage:
#   ./scripts/verify.sh

set -euo pipefail

DOLT_POD=$(kubectl get pod -l app=dolt-db -o jsonpath='{.items[0].metadata.name}')

echo "=== Dolt branches ==="
kubectl exec "${DOLT_POD}" -c dolt -- \
  bash -c "cd /var/lib/dolt/location && dolt branch -a"
echo ""

echo "=== Location data on main ==="
kubectl exec "${DOLT_POD}" -c dolt -- \
  bash -c "cd /var/lib/dolt/location && dolt sql -q 'SELECT * FROM locations;'"
echo ""

echo "=== Location service health ==="
kubectl exec "${DOLT_POD}" -- \
  bash -c "apt-get update -qq > /dev/null 2>&1 && apt-get install -y -qq curl > /dev/null 2>&1 && curl -s http://location-service.default.svc:3000/health" 2>/dev/null || \
  echo "(Could not reach location service from Dolt pod)"
echo ""

echo "=== Sandbox status ==="
signadot sandbox get dolt-sandbox-demo -o yaml 2>/dev/null || echo "No sandbox found."
echo ""

echo "=== Verification complete ==="