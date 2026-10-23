#!/bin/bash
# Creates the products_fg sandbox and registers its WunderGraph feature flag.
# Usage: CLUSTER=<your-signadot-cluster> ./sandbox.sh
set -euo pipefail

: "${CLUSTER:?Set CLUSTER to your cluster name in Signadot}"

signadot sandbox apply -f - <<EOF
name: wundergraph-products
spec:
  cluster: ${CLUSTER}
  forks:
    - forkOf:
        kind: Deployment
        namespace: wundergraph-demo
        name: products
      customizations:
        images:
          - image: signadot/wundergraph-demo-products_fg:latest
        env:
        - name: PORT
          value: "4004"
EOF

# Once the sandbox is ready, register the feature flag, named after its routing key
ROUTING_KEY=$(signadot sandbox get wundergraph-products -o json | jq -r .routingKey)

cd ~/git/third-party/wundergraph/cosmo/demo

wgc feature-subgraph create "products-${ROUTING_KEY}" \
 --namespace development \
 --routing-url http://products.wundergraph-demo.svc:4004/graphql \
 --subgraph products

wgc subgraph publish "products-${ROUTING_KEY}" \
    --namespace development \
    --schema ./pkg/subgraphs/products_fg/subgraph/schema.graphqls

wgc feature-flag create "${ROUTING_KEY}" \
    --namespace development \
    --feature-subgraphs "products-${ROUTING_KEY}" \
    --enabled
