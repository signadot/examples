# Temporal Sandbox Example

This example demonstrates how to use **Temporal** workflows together with Signadot
Sandboxes. The project contains a simple bank transfer workflow written in
Python using the `temporalio` SDK.

Two versions of the worker are provided. Version `v1` performs a transfer using
`withdraw` and `deposit` activities. Version `v2` adds a `fraud_check`
activity. Signadot sandboxes are used to route workflow tasks to the desired
worker version.

The `client` directory contains a small FastAPI application with a simple
web-based form that starts a bank transfer workflow. The `worker` directories
implement the Temporal workers.
Routing logic is implemented via workflow and activity interceptors which query
Signadot's RouteServer.

Kubernetes manifests for deploying Temporal and the demo services are available
in the `k8s` directory. Example sandbox specifications can be found under the
`signadot` directory.


## Directory Structure

- `client` - FastAPI application that starts a workflow.
- `worker` - Worker implementation with withdraw and deposit activities.
- `worker_v2` - Worker with an additional fraud check activity.
- `platform` - Interceptors and RouteServer client used by workers.
- `k8s` - Kubernetes manifests for Temporal and baseline deployments.
- `signadot` - Sandbox and routegroup specifications.

## Running

1. Install the Signadot operator in your Kubernetes cluster.
2. Apply the manifests under `k8s` to deploy Temporal and baseline services.
3. Build images for the client and workers and push them to a registry accessible
   by the cluster.
4. Create sandboxes using the specs in `signadot/sandboxes` and a routegroup
   using `signadot/routegroups/temporal.yaml`.
5. Access the client using the preview URL from the sandbox (visit `/` to use
   the HTML form) or via the Signadot browser extension. Selecting the worker
   sandbox in the extension will add the
   routing key to the request. The routing interceptors ensure the workflow runs
   on the selected worker version.
