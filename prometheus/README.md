# Signadot Prometheus-operator integration example

This directory contains source files for configuring [Prometheus](https://prometheus.io)
to monitor the Signadot Operator using ServiceMonitors.

It contains:
- a prometheus CR with config to point to ServiceMonitors in the signadot namespace 
- service monitors for Signadot Operator metrics services
- RBACs for prometheus.

## Setup

1. Install prometheus (in namespace default)
1. Give the signadot namespace a label "prometheus: signadot"
1. kubectl apply -f rbac.yaml
1. kubectl apply -f prometheus.yaml
1. kubectl apply -f svcmon.yaml

## Usage

Point your browser to the in-cluster endpoint prometheus-operated.default.svc:9090.
This should provide access to graphing, querying, and setting up alerts for the metrics 
associated with the Signadot Operator.




