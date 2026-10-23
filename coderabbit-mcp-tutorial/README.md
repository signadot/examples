# Runtime-Aware Code Review with CodeRabbit and Signadot MCP

Boxoffice is a small seat-hold application with storefront, inventory and pricing services. A pull
request changes one service, and Signadot runs that change in a sandbox while the other services
stay on the baseline.

For the guided step-by-step walkthrough, see the
[full tutorial](https://www.signadot.com/docs/tutorials/coderabbit-signadot-mcp).

| Service | Responsibility | Dependency |
| --- | --- | --- |
| storefront | Validate a request, acquire a hold, return a quote | inventory, pricing |
| inventory | Own seats, enforce idempotency, expire holds | PostgreSQL |
| pricing | Calculate integer minor-unit amounts and cache quotes | Redis |

## What's in this directory

Copy the whole directory, including dotfiles, to the root of your own repository. GitHub only runs
workflows from a repository root.

| Path | Purpose |
| --- | --- |
| `pkg/`, `docker/`, `db/`, `k8s/` | The three services, their images, the database schema and seed data, and the Kubernetes manifests |
| `lessons/` | The two storefront changes the tutorial opens as pull requests |
| `smart-tests/reservations/create-reservation.star` | The reservation test the tutorial saves as a hosted Smart Test |
| `signadot/pr-sandbox.yaml` | The sandbox template for a pull request's image |
| `scripts/sandbox-name.cjs` | Computes the sandbox name from the repository, pull request and commit |
| `.github/workflows/build-pr-image.yml` | Builds a pull request's latest commit and records its image digest |
| `.coderabbit.yaml` | Turns on CodeRabbit's MCP context and detailed reviews |

## Run the application

You need a minikube cluster connected to Signadot with the
[Signadot Operator](https://www.signadot.com/docs/installation/signadot-operator), plus Docker,
`kubectl` and `make`:

```bash
make images
make deploy KUBE_CONTEXT=minikube
kubectl --context minikube -n boxoffice get pods
```

`make images` builds the three service images and loads them into minikube. `make deploy` seeds
`show-1` with 36 seats and waits for all five deployments. Storefront, inventory and pricing should
show `2/2` containers ready (the application plus its DevMesh sidecar), and PostgreSQL and Redis
should each show `1/1`.

## Reservation contract

`POST /reservations` takes a show, seats, currency and idempotency key. It should return a held
reservation and a quote including fees, reuse an active hold for the same request, and return `409`
when another request tries to reserve those seats.

The Smart Test checks five parts of that contract. It reserves seats B11 and B12 in the shared demo
database, so leave those seats alone. Holds last 24 hours in this demo (`HOLD_SECONDS`), so repeated
test runs reuse the same hold.

## Cleanup

Delete the sandboxes you created and the `boxoffice-reservation-contract` hosted test when you are
finished. This
command deletes the application namespace and its database contents:

```bash
make clean KUBE_CONTEXT=minikube
```
