#!/bin/bash
set -e

cd ~/git/thrid-party/wundergraph/cosmo/demo

# Create the federated graph
wgc federated-graph create demo \
    --namespace development \
    --routing-url http://router.wundergraph-demo.svc:3002/graphql


# Create the products subgraph
wgc subgraph create products \
    --namespace development \
    --routing-url http://products.wundergraph-demo.svc:4004/graphql
wgc subgraph publish products \
    --namespace development \
    --schema ./pkg/subgraphs/products/subgraph/schema.graphqls


# Create the employees subgraph
wgc subgraph create employees \
    --namespace development \
    --routing-url http://employees.wundergraph-demo.svc:4001/graphql
wgc subgraph publish employees \
    --namespace development \
    --schema ./pkg/subgraphs/employees/subgraph/schema.graphqls


# Create the mood subgraph
wgc subgraph create mood \
    --namespace development \
    --routing-url http://mood.wundergraph-demo.svc:4008/graphql
wgc subgraph publish mood \
    --namespace development \
    --schema ./pkg/subgraphs/mood/subgraph/schema.graphqls


# Create the availability subgraph
wgc subgraph create availability \
    --namespace development \
    --routing-url http://availability.wundergraph-demo.svc:4007/graphql
wgc subgraph publish availability \
    --namespace development \
    --schema ./pkg/subgraphs/availability/subgraph/schema.graphqls
