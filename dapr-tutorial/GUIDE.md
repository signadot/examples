# Student Guide: Dapr + Signadot Tutorial

This guide is for you, the person taking the bootstrap in this directory and
turning it into a tutorial that anyone can run end to end. It assumes you know
Kubernetes basics and are new to both Signadot and Dapr.

Your mission, in one sentence: **prove, on a real cluster, that a Dapr
application can be tested with Signadot sandboxes for both synchronous calls and
pub/sub, then write it up so a reader can repeat it in under an hour.**

## 1. The mental model (read this first)

**Signadot.** In a shared Kubernetes cluster ("the baseline"), you want to test
your change to one service without redeploying everything. Signadot forks just
that service into a *sandbox*: a copy of the Deployment running your image next
to the baseline. Requests that carry the sandbox's *routing key* (an opaque
string in the `baggage` HTTP header as `sd-routing-key=<key>`) are routed to
your fork; all other requests keep going to the baseline. Routing is done at the
destination by a small sidecar (DevMesh) injected into baseline pods, or by a
service mesh such as Istio. For async messaging there is no request to route,
so consumers themselves read the key from each message and ask Signadot's
Routes API "is this one mine?".

**Dapr.** Each app gets a sidecar (`daprd`). The app talks only to its local
sidecar over HTTP on `localhost:3500`. To call another app, it asks the sidecar
to `invoke/<app-id>`; the sidecar finds the target's sidecar and forwards the
request. To publish, it asks the sidecar to `publish/<pubsub>/<topic>`; the
sidecar wraps the payload in a CloudEvent and hands it to the broker. To
subscribe, the app tells its sidecar which topics it wants and the sidecar
POSTs each message to the app. An app is identified by its *app-id*, set with a
pod annotation.

**Why they collide.** Signadot routes by looking at headers on the wire between
pods. Dapr hides that wire: the sidecar-to-sidecar hop is gRPC with the original
headers packed inside a protobuf message, and the app-id (not a Kubernetes
Service) is the unit of addressing. Almost every design decision in this
tutorial follows from those two facts.

**The two use cases.**
1. *Service invocation*: frontend invokes `checkout`; with a routing key the
   sandboxed checkout must answer.
2. *Pub/sub*: checkout publishes an order; with a routing key the sandboxed
   order-processor must process it and the baseline must skip it.

## 2. Reading list

Read in this order. Each item says what to look for.

Signadot
- [Sandboxes concept](https://www.signadot.com/docs/concepts/sandbox): what a fork is, what a routing key is.
- [Header-based routing](https://www.signadot.com/docs/guides/set-up-context-propagation): the exact headers (`baggage`, `tracestate`) and why services must forward them.
- [DevMesh](https://www.signadot.com/docs/guides/request-routing/devmesh): the sidecar that routes at the destination; how to enable it per pod.
- [Kafka message isolation guide](https://www.signadot.com/docs/guides/set-up-message-queue-isolation/kafka): the selective-consumption pattern we copy for Dapr pub/sub.
- [Sandbox spec](https://www.signadot.com/docs/reference/sandboxes/spec): especially `forks[].customizations.patch`.
- [Routes API](https://github.com/signadot/routesapi): read `docs/sandbox-routing.md` and `docs/workload-rules.md`; the REST endpoint is at `routeserver.signadot.svc:7778`.
- [Resource plugins](https://www.signadot.com/docs/reference/resource-plugins/spec) and the [k8s-apply plugin](https://github.com/signadot/plugins/tree/main/k8s-apply): how a sandbox can create extra Kubernetes objects.
- In this repo: [`selective-consumption-with-kafka`](../selective-consumption-with-kafka) and [`temporal-tutorial`](../temporal-tutorial). Our code mirrors their decision logic.

Dapr
- [Overview](https://docs.dapr.io/concepts/overview/) and [Kubernetes hosting](https://docs.dapr.io/operations/hosting/kubernetes/kubernetes-overview/): what operator, injector, sentry do.
- [Service invocation](https://docs.dapr.io/developing-applications/building-blocks/service-invocation/service-invocation-overview/) and [invoking non-Dapr endpoints (HTTPEndpoint)](https://docs.dapr.io/developing-applications/building-blocks/service-invocation/howto-invoke-non-dapr-endpoints/): the resource we use for use case 1.
- [Pub/sub overview](https://docs.dapr.io/developing-applications/building-blocks/pubsub/pubsub-overview/), [subscription methods](https://docs.dapr.io/developing-applications/building-blocks/pubsub/subscription-methods/), [CloudEvents](https://docs.dapr.io/developing-applications/building-blocks/pubsub/pubsub-cloudevents/): why programmatic subscriptions, and how custom CloudEvent attributes pass through.
- [Pod annotations](https://docs.dapr.io/reference/arguments-annotations-overview/): `dapr.io/app-id`, `app-port`, `config`.
- [W3C tracing and baggage](https://docs.dapr.io/operations/observability/tracing/w3c-tracing-overview/): needed for the `tracestate` variation.
- [Name resolution](https://docs.dapr.io/reference/components-reference/supported-name-resolution/) and [Configuration](https://docs.dapr.io/operations/configuration/configuration-overview/): background for research task R2.

## 3. What we already established

These were checked by reading Dapr's source (`dapr/dapr` and
`dapr/components-contrib` on GitHub, `master` as of September 2026). Re-verify
anything you rely on against the Dapr version you install; file paths are given
so you can look.

| # | Fact | Where |
|---|---|---|
| F1 | The injector adds pod labels `dapr.io/app-id` and `dapr.io/sidecar-injected`. | `pkg/injector/patcher/sidecar_patcher.go` |
| F2 | The operator creates a headless Service `<app-id>-dapr` whose selector is the Deployment's `matchLabels`; if the Service exists it is *updated* to the current Deployment, including its ownerReference. Two Deployments with one app-id fight over it. | `pkg/operator/handlers/dapr_handler.go`, `ensureDaprServicePresent` |
| F3 | The sidecar-to-sidecar call (`CallLocalStream`, port 50002) carries only `traceparent` and `grpc-trace-bin` as gRPC metadata. `baggage` and `tracestate` are inside the protobuf and are re-emitted as HTTP headers to the target app. | `pkg/messaging/direct_messaging.go` (`invokeRemote`, `setContextSpan`), `pkg/diagnostics/grpc_tracing.go` (`SpanContextToGRPCMetadata`), `pkg/messaging/v1/util.go` (`InternalMetadataToHTTPHeader`) |
| F4 | The callee sidecar does not check that the callee app-id matches its own; only access-control policies are evaluated. | `pkg/api/grpc/daprinternal.go` |
| F5 | `Invoke` checks HTTPEndpoint names *before* app-id resolution, so an HTTPEndpoint named like an app-id wins. Headers are forwarded to the endpoint. | `pkg/messaging/direct_messaging.go` (`Invoke`), `pkg/channel/http/http_channel.go` |
| F6 | Pub/sub does not propagate `baggage`. It does copy the publisher's span `tracestate` into the CloudEvent (only when tracing is enabled) and delivers it as a header. | `pkg/api/http/http.go` (`onPublish`), `pkg/runtime/subscription/subscription.go` |
| F7 | A publisher-supplied CloudEvent (`Content-Type: application/cloudevents+json`) keeps unknown attributes. | `components-contrib/pubsub/envelope.go` (`FromCloudEvent`) |
| F8 | Message metadata is delivered to HTTP subscribers as headers. With Kafka, record headers become metadata and publish metadata becomes record headers. | `pkg/runtime/subscription/postman/http/http.go`, `components-contrib/common/component/kafka/{producer,consumer}.go` |
| F9 | Kafka and Redis Streams components default the consumer group to the app-id. | Dapr component docs |
| F10 | Signadot injects `SIGNADOT_SANDBOX_NAME` into forked pods; the Kafka and Temporal examples rely on it. | this repo |

## 4. Set up your environment

1. `minikube start --cpus 4 --memory 6g`
2. Install the Dapr CLI, then `dapr init -k --wait`. Check with `kubectl -n dapr-system get pods`.
3. Install the Signadot operator following the [installation docs](https://www.signadot.com/docs/installation/signadot-operator); connect the cluster in the Signadot dashboard; install and log in with the Signadot CLI. Check with `kubectl -n signadot get pods`.
4. Install the [Signadot browser extension](https://www.signadot.com/docs/browser-extensions) so you can switch routing keys while looking at the UI.

Then follow the Quick start in [README.md](README.md). Do not skip the baseline
test; if the app does not work without sandboxes, nothing else will.

Useful commands while debugging:

```bash
kubectl -n dapr-demo get pods -o wide --show-labels
kubectl -n dapr-demo logs deploy/checkout -c daprd          # Dapr sidecar logs (API logging is on)
kubectl -n dapr-demo logs deploy/checkout -c sd-sidecar     # Signadot DevMesh sidecar logs
kubectl -n dapr-demo get svc                                 # look for <app-id>-dapr services
kubectl -n dapr-demo get httpendpoints,components,subscriptions
signadot sandbox get dapr-order-processor-sbx
# Ask the Routes API what it knows about a workload:
kubectl -n dapr-demo run -it --rm curl --image=curlimages/curl --restart=Never -- \
  curl -s 'http://routeserver.signadot.svc:7778/api/v1/workloads/routing-rules?baselineKind=Deployment&baselineNamespace=dapr-demo&baselineName=order-processor'
```

## 5. Verification checklist

Work through these in order and record the result (command run, what you saw,
date, Dapr and Signadot operator versions) in a `FINDINGS.md` next to this file.
"Expected" describes success; when reality differs, that is a finding, not a failure.

| # | Check | How | Expected |
|---|---|---|---|
| V1 | All three sidecars coexist | `kubectl -n dapr-demo get pods` | checkout and order-processor `3/3`; container names include `daprd` and `sd-sidecar` |
| V2 | Baseline flow works | Port-forward the frontend, place an order | `handled_by.app_id=checkout`, `processed_by=order-processor` |
| V3 | Dapr Services for the fork | Create `sandbox-order-processor.yaml`, then `kubectl -n dapr-demo get svc -o wide` | `order-processor-dapr` still selects the baseline pod; a new `order-processor-sbx-dapr` selects the fork pod |
| V4 | Fork identity | `kubectl -n dapr-demo exec <fork pod> -c order-processor -- env \| grep SIGNADOT` | `SIGNADOT_SANDBOX_NAME=dapr-order-processor-sbx` |
| V5 | Use case 2, sandbox key | Open the order-processor sandbox preview URL, place an order; tail both consumers' logs | fork logs `processed`, baseline logs `skip`; UI shows `processed_by=order-processor-sbx` |
| V6 | Use case 2, no key | Port-forward again, place an order | baseline `processed`, fork `skip` |
| V7 | Use case 1 | Create `sandbox-checkout.yaml`; open its preview URL, place an order | `handled_by.app_id=checkout-sbx`; the order is processed by the *baseline* order-processor |
| V8 | Route group | Apply `routegroup.yaml`, use its URL | `checkout-sbx` and `order-processor-sbx` together |
| V9 | Header forwarding through HTTPEndpoint | Temporarily log `request.headers` in checkout | the `baggage` header arrives at the callee |
| V10 | Dapr's native hop still works next to DevMesh | Delete the `order-processor` HTTPEndpoint, reload the UI (frontend now invokes via sidecar-to-sidecar gRPC, port 50002) | processed list still loads; routing by key no longer works for that call. Re-apply afterwards |
| V11 | No message replay | Create a fresh order-processor sandbox after orders exist | the new fork does not process old orders (Redis Streams starts at latest) |
| V12 | Deliberate failure: same app-id | In a scratch namespace, deploy two Dapr Deployments with the same app-id; inspect the `-dapr` Service selector and ownerReferences over a minute | selector flips between the two; deleting one Deployment deletes the Service. Write this up as the motivating gotcha |
| V13 | Kafka variant | Follow the steps in `k8s/dapr/pubsub-kafka.yaml` | V5 and V6 pass unchanged |
| V14 | `tracestate` variant | Add a Dapr `Configuration` with `tracing.samplingRate: "1"` and `dapr.io/config` on the pods; remove the `baggage` attribute in checkout | V5 still passes via the `tracestate` fallback, or you document why not |

## 6. Research tasks

Each task is a question we could not fully answer from docs and source alone.
Time-box them; a clear "does not work, because" is a valid result.

**R1. Where exactly does DevMesh intercept?** Does the DevMesh sidecar redirect
every inbound port or only ports that have a Kubernetes Service? The Dapr
sidecar's ports (3500, 50001, 50002) do have one (`<app-id>-dapr`). Check the
sd-sidecar logs and the pod's iptables rules (an init container usually sets
them) and confirm that Dapr's mTLS traffic on 50002 passes through untouched
(V10 covers the functional side). Also check mutating-webhook ordering:
`kubectl get mutatingwebhookconfigurations` and the order of containers in the
pod. If Signadot's webhook runs before Dapr's, it never sees the Dapr ports.

**R2. Can Dapr's own routing be configured to reach a sandbox, without code
changes and without HTTPEndpoint?** The honest baseline answer is no, because of
F3, but document the attempts so the tutorial can say why:
- Name resolution: the Kubernetes resolver has a `template`, and 1.16 added a
  `nameformat` resolver. Both are static per sidecar and cannot vary per request.
- HTTP middleware (`httpPipeline` in a Configuration): `routeralias` rewrites
  paths statically; `wasm` can rewrite headers and URIs but cannot make network
  calls; `opa` can call `http.send` from Rego but can only allow, deny, or add
  headers. Try whether an OPA policy that sets `dapr-app-id` affects a
  header-style invocation; even if it does, path-style `/v1.0/invoke/...` calls
  and gRPC calls are unaffected, so it is not a general solution.
- Signadot resource plugins run at sandbox creation and can create Kubernetes
  objects, so they cannot influence per-request routing. They *are* the right
  tool for R4.

**R3. Caller-side alternative that keeps Dapr's native hop.** Prototype a
20-line helper in `app/signadot/` that, before `invoke/<app-id>`, reads the
routing key, asks the Routes API whether a sandbox of that app's Deployment
claims the key (`destinationSandbox.name` is in the response), and rewrites the
target to `<app-id>-<sandbox-name>`. This keeps mTLS on the hop but requires
callers to opt in and a naming convention for sandbox app-ids. Compare with the
HTTPEndpoint approach in a short pros/cons table for the README.

**R4. Declarative subscriptions with scopes.** Convert order-processor to a
declarative `Subscription` scoped to `order-processor` and confirm the fork
gets nothing. Then fix it two ways: add the fork's app-id to `scopes`, and use
the `k8s-apply` resource plugin from a sandbox spec to create a
`Subscription` scoped to `order-processor-sbx` with owner references to the
sandbox. The second is a nice showcase of resource plugins.

**R5. State store key prefix.** Add a Dapr state store (Redis) and have
order-processor save each processed order. Show that the fork's keys are
prefixed with its app-id by default, and what changes with `keyPrefix: name`.

**R6. Istio mode.** If you have time, install Istio, switch the Signadot
operator to Istio routing, and check whether the HTTPEndpoint hop routes via
the VirtualService that Signadot manages for the `checkout` Service.

**R7. Upstream proposal.** Draft (do not submit until reviewed) a Dapr issue
proposing that `invokeRemote` add the request's `baggage` (and `tracestate`)
to the outgoing gRPC metadata. Explain the use case; point at F3 and F4. This
would let DevMesh route the native hop with no HTTPEndpoint.

**R8. Local development.** Investigate `signadot local connect` with a Dapr
sidecar running on the laptop (`dapr run`): which name resolver would let the
local sidecar reach cluster apps, and can the cluster reach the local app?

## 7. Working style and deliverables

- Keep `FINDINGS.md` as a running log. Every checklist item gets a line.
- When you change code, keep it as small and readable as it is now. The
  platform layer stays in `app/signadot/`; application files must not import
  anything Signadot-specific beyond what they do today.
- Update README.md as you go: remove 🔍 marks when verified, fix commands that
  did not work exactly as written, and add screenshots of the UI in the three
  routing situations (no key, checkout sandbox, route group).
- Commit small and often on this branch. Prefix messages with `dapr-tutorial:`.
- Ask early when stuck for more than an hour on cluster setup; that is not the
  interesting part.

Done looks like this: a colleague with a fresh minikube follows README.md only,
finishes in under an hour, sees the four rows of the routing table behave as
described, and the Gotchas section explains every surprise they might hit.
