#!/bin/bash
# Prints a Signadot sandbox spec that forks each changed HotROD service with the PR image.
# Usage: sandbox.sh <name> <cluster> <image> <pr-id> <service>...
set -euo pipefail
name="$1" cluster="$2" image="$3" pr="$4"
shift 4
cat <<EOF
name: ${name}
spec:
  cluster: ${cluster}
  description: "HotROD PR #${pr}"
  labels:
    bitbucket-pull-request: "${pr}"
  ttl:
    duration: 3d
    offsetFrom: updatedAt
  forks:
EOF
for svc in "$@"; do
  cat <<EOF
    - forkOf:
        kind: Deployment
        namespace: hotrod
        name: ${svc}
      customizations:
        images:
          - container: hotrod
            image: ${image}
EOF
done
cat <<EOF
  defaultRouteGroup:
    endpoints:
      - name: frontend
        target: http://frontend.hotrod.svc:8080
EOF
