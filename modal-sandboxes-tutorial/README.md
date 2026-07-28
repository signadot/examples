# Background Coding Agents: End-to-End Testing with Modal Sandboxes and Signadot

## Prerequisites

- A Kubernetes cluster with the [Signadot Operator](https://www.signadot.com/docs/getting-started/installation/signadot-operator) installed
- The [HotROD demo app](https://github.com/signadot/hotrod) deployed in the cluster:
  ```bash
  kubectl create ns hotrod --dry-run=client -o yaml | kubectl apply -f -
  kubectl -n hotrod apply -k 'https://github.com/signadot/hotrod/k8s/overlays/prod/istio'
  ```
- A [Signadot account](https://www.signadot.com/) and an API key (Dashboard → Settings → API Keys)
- A [Modal](https://modal.com/) account with the CLI installed locally (`pip install modal && modal token new`)
- A Claude subscription (for `claude setup-token`) or an Anthropic API key, to run [Claude Code](https://code.claude.com/docs/) inside the sandbox

## Overview

Coding agents work best when they can *test* what they build. On a laptop, Signadot's
[local sandboxes](https://www.signadot.com/docs/tutorials/quickstart/local-development) solve this: run one
service locally, connect it to a shared staging cluster, and end-to-end test your change with
request-level isolation — no full-stack replica needed. But agents increasingly don't run on laptops.
[Modal Sandboxes](https://modal.com/docs/guide/sandbox) are secure, ephemeral cloud containers made for
running agent code — spin one up in seconds, throw it away after. The question is how code running there
gets tested against real dependencies.

This tutorial combines the two: a Modal Sandbox acts as the developer's "local" environment — running
Claude Code, the Signadot CLI, and the service under development — while Signadot routes request-tagged
traffic from the staging cluster into it. Your laptop is reduced to a thin client (`modal shell`); the dev
environment itself is disposable cloud infrastructure.

Two properties make this work with nothing but an API key:

1. **ControlPlaneProxy connectivity.** The Signadot CLI's `ControlPlaneProxy` connection type routes all
   cluster communication through the Signadot Control Plane. The Modal sandbox needs no kubeconfig, no
   VPN, and no network path to the cluster API — only `SIGNADOT_ORG` and `SIGNADOT_API_KEY`. (It is
   rate-limited and intended for setup/evaluation; see [Production connectivity](#production-connectivity-options).)
2. **Unprivileged local connect.** Modal sandboxes run on gVisor, which doesn't implement netfilter NAT,
   so Signadot's privileged networking (virtual IPs + cluster DNS) is unavailable. `signadot local connect
   --unprivileged` works without it: inbound tunneling for local sandboxes functions normally, and
   outbound access to in-cluster services goes through explicit `signadot local proxy` port mappings.

## What You Will Build

You will launch a Modal Sandbox provisioned with Go, Claude Code, and the Signadot CLI, connected to a
staging cluster running HotROD. Inside it, Claude Code modifies the `route` service (making every computed
ETA exactly 2 minutes — an intentionally visible change), a Signadot sandbox maps the in-cluster `route`
Deployment to `localhost:8083` in the Modal sandbox, and you prove end to end that requests carrying the
sandbox routing key get the new behavior — propagated through HTTP → Kafka → gRPC — while baseline
traffic is untouched.

The tutorial ships four files:

```
launch_sandbox.py       Modal app: image definition + sandbox launcher
in-sandbox/setup.sh     runs at launch: Signadot CLI config + local connect
in-sandbox/CLAUDE.md    context for Claude Code inside the sandbox
local-route.yaml        Signadot sandbox spec (local workload mapping)
```

```mermaid
---
config:
  theme: default
  flowchart:
    nodeSpacing: 40
    rankSpacing: 60
    padding: 12
  themeVariables:
    fontSize: 14px
    fontFamily: monospace
---
flowchart TB
    Dev["Developer laptop<br/>(modal shell — thin client)"]
    subgraph ModalSB["Modal Sandbox (ephemeral cloud dev env)"]
        CC["Claude Code"]
        CLI["signadot CLI<br/>local connect --unprivileged"]
        RouteV2["route service v2<br/>localhost:8083"]
    end
    CP["Signadot Control Plane"]
    subgraph Cluster["Staging cluster (baseline HotROD)"]
        Op["Signadot Operator"]
        FE["frontend"]
        Kafka["Kafka"]
        Driver["driver"]
        RouteV1["route (baseline)"]
    end

    Dev -- "modal shell" --> ModalSB
    CLI <-- "ControlPlaneProxy<br/>(API key only)" --> CP
    CP <--> Op
    FE -- "dispatch" --> Kafka
    Kafka --> Driver
    Driver -- "no routing key" --> RouteV1
    Driver -- "routing key: tunnel to<br/>Modal sandbox" --> Op
    Op -. "via control plane" .-> RouteV2

    style Dev fill:#f5f5f5,stroke:#333,stroke-width:2px,color:#111
    style ModalSB fill:#e8eef4,stroke:#336,stroke-width:2px,color:#111
    style CP fill:#e4efe4,stroke:#363,stroke-width:2px,color:#111
    style Cluster fill:#faf5e6,stroke:#663,stroke-width:2px,color:#111
    style RouteV2 fill:#dce8dc,stroke:#363,stroke-width:2px,color:#111
    style RouteV1 fill:#f0e8e0,stroke:#633,stroke-width:2px,color:#111
```

HotROD's request flow makes this a strong test of routing-context propagation: `frontend` publishes
dispatch requests to **Kafka**, `driver` consumes them and calls `route` over **gRPC**, and results
surface as notifications. The routing key travels the whole path in OpenTelemetry baggage, and the
Signadot Operator routes the driver→route hop into your Modal sandbox.

## Step 1: Create the Modal secrets

Credentials enter the sandbox only as [Modal Secrets](https://modal.com/docs/guide/secrets) — nothing is
baked into the image.

```bash
modal secret create signadot-credentials SIGNADOT_ORG=<your-org> SIGNADOT_API_KEY=<your-api-key>
```

For Claude Code, either use your Claude subscription (run `claude setup-token` on your laptop and copy the
long-lived token it prints):

```bash
modal secret create claude-code-auth CLAUDE_CODE_OAUTH_TOKEN=<token>
```

or use an Anthropic API key instead:

```bash
modal secret create claude-code-auth ANTHROPIC_API_KEY=<key>
```

Claude Code picks up whichever variable is present.

## Step 2: Launch the cloud dev environment

[`launch_sandbox.py`](launch_sandbox.py) defines the image and creates the sandbox. The image is plain
`debian_slim` plus the dev toolchain:

```python
image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("git", "curl", "ca-certificates", "vim", "procps", "lsof", "jq")
    .run_commands(
        # Go toolchain (HotROD services are written in Go). Symlink into
        # /usr/local/bin so login shells (modal shell) find it regardless of
        # profile PATH resets.
        f"curl -fsSL https://go.dev/dl/go{GO_VERSION}.linux-amd64.tar.gz | tar -C /usr/local -xz",
        "ln -s /usr/local/go/bin/go /usr/local/bin/go && ln -s /usr/local/go/bin/gofmt /usr/local/bin/gofmt",
        # Node.js 22 + Claude Code
        "curl -fsSL https://deb.nodesource.com/setup_22.x | bash -",
        "apt-get install -y nodejs",
        "npm install -g @anthropic-ai/claude-code",
        # Signadot CLI
        "curl -sSLf https://raw.githubusercontent.com/signadot/cli/main/scripts/install.sh | sh",
    )
    ...
)
```

The launcher attaches the secrets and — importantly — creates the sandbox against a *persistent* app so
it outlives the `modal run` invocation:

```python
    # Create the sandbox against a persistent (deployed) app so it outlives
    # this `modal run` invocation. Sandboxes attached to the ephemeral run
    # app would be terminated as soon as this entrypoint returns.
    sandbox_app = modal.App.lookup("signadot-dev-env", create_if_missing=True)
    sb = modal.Sandbox.create(
        image=image,
        app=sandbox_app,
        secrets=[
            modal.Secret.from_name("signadot-credentials"),
            modal.Secret.from_name("claude-code-auth"),
        ],
        timeout=4 * 60 * 60,  # 4h interactive dev session
        cpu=2,
        memory=4096,
    )
```

After creating the sandbox, the launcher runs [`in-sandbox/setup.sh`](in-sandbox/setup.sh), which handles
two gVisor-specific quirks and connects:

```bash
# gVisor (the Modal sandbox runtime) exposes neither /etc/machine-id nor
# /proc/sys/kernel/random/uuid, which the Signadot CLI uses to identify this
# "machine". Generate one for this sandbox.
if [ ! -s /etc/machine-id ]; then
    python3 -c "import uuid; open('/etc/machine-id','w').write(uuid.uuid4().hex + '\n')"
fi

mkdir -p "$HOME/.signadot"
cat > "$HOME/.signadot/config.yaml" <<EOF
local:
  connections:
  - cluster: ${CLUSTER}
    type: ControlPlaneProxy
EOF

# --unprivileged: gVisor does not implement netfilter NAT, so the privileged
# localnet setup (virtual IPs + cluster DNS) is unavailable.
signadot local connect --unprivileged --wait connect --wait-timeout 120s
```

Note that the CLI needs no `signadot auth login` here: it reads `SIGNADOT_ORG` and `SIGNADOT_API_KEY`
straight from the environment, which the Modal secret provides.

Launch it (replace `demo` with your cluster name as registered in Signadot):

```bash
modal run launch_sandbox.py --cluster demo
```

The first run builds the image (~2 minutes); later launches reuse it and start in seconds. Output ends
with:

```
Sandbox created: sb-Dx4LUDetYGvzz2DqKJMjE5
Running Signadot setup (local connect)...
signadot local connect has been started ✓
✓ Local connection healthy!
    * operator version 1.3.2
    * devbox 4a0e7f2218ae964ef68b08405c959d7b connected
    * sandboxes watcher is running

Connect with:  modal shell sb-Dx4LUDetYGvzz2DqKJMjE5
```

## Step 3: Shell in

```bash
modal shell sb-Dx4LUDetYGvzz2DqKJMjE5
```

You get an interactive root shell inside the sandbox — this is "the laptop". Everything from here on runs
inside it. (`/root/workspace/` contains a `CLAUDE.md` describing this workflow to Claude Code, plus the
sandbox spec.)

## Step 4: Create the Signadot sandbox

[`local-route.yaml`](local-route.yaml) declares a sandbox whose only workload is *local* — the in-cluster
`route` Deployment mapped to a port inside this Modal sandbox:

```yaml
name: modal-route-dev
spec:
  description: HotROD route service under development in a Modal sandbox
  cluster: "@{cluster}"
  ttl:
    duration: 1d
  local:
  - name: modal-route
    from:
      kind: Deployment
      namespace: "@{namespace}"
      name: route
    mappings:
    - port: 8083
      toLocal: "localhost:8083"
  defaultRouteGroup:
    endpoints:
    - name: frontend
      target: "http://frontend.@{namespace}.svc:8080"
```

Apply it from inside the Modal sandbox:

```bash
signadot sandbox apply -f /root/workspace/local-route.yaml --set cluster=demo --set namespace=hotrod
```

```
Created sandbox "modal-route-dev" (routing key: ug86wvt9f5nhq) in cluster "demo".
✓ Sandbox status: Ready: All desired workloads are available.

Dashboard page: https://app.signadot.com/sandbox/name/modal-route-dev

SANDBOX ENDPOINT   TYPE   URL
frontend           host   https://frontend--modal-route-dev.preview.signadot.com
```

`signadot local status` now shows the tunnel bound to this environment:

```
* Mapped Sandboxes:
    - modal-route-dev
        * Routing Key: ug86wvt9f5nhq
        - modal-route: routing from Deployment/route in namespace "hotrod"
            - remote port 8083 -> localhost:8083
        ✓ connection ready
```

From this moment, any request in the cluster that carries the routing key `ug86wvt9f5nhq` and reaches the
`route` service is tunneled to `localhost:8083` *inside the Modal sandbox*. Nothing is listening there
yet — that's next.

## Step 5: Let the agent make a change

Clone HotROD and hand the task to Claude Code:

```bash
git clone https://github.com/signadot/hotrod /root/workspace/hotrod
cd /root/workspace/hotrod
claude
```

In the interactive session, ask for a deliberately visible change:

> In services/route/server.go, change the ETA computation so every computed ETA is exactly 2 minutes.
> Keep the FAST_ROUTE override and rounding logic intact. Smallest possible diff.

(The same works headlessly: `claude -p "<prompt>" --allowedTools "Edit,Read,Glob,Grep"`.) The resulting
diff:

```diff
-	// Generate a random number between 3 and 45 with decimals
-	eta := time.Duration((rand.Float64()*(45-3) + 3) * float64(time.Minute))
+	eta := 2 * time.Minute
 	if os.Getenv("FAST_ROUTE") != "" {
 		eta = time.Second
 	}
```

Baseline ETAs are random between 3 and 45 minutes, so an ETA of exactly `2m0s` can only come from this
code.

## Step 6: Run the service

```bash
cd /root/workspace/hotrod
ROUTE_CALC_DELAY=1ms go run ./cmd/hotrod/main.go route > /root/route.log 2>&1 &
```

`ROUTE_CALC_DELAY=1ms` matters: HotROD's driver service calls route with a 1-second gRPC timeout per call,
and calls tunneled through the ControlPlaneProxy already carry a few hundred milliseconds of extra
latency. Skipping the service's simulated 50 ms "calculation delay" keeps every call comfortably inside
that budget.

## Step 7: Test end to end

In unprivileged mode there's no cluster DNS, so open two `signadot local proxy` mappings to the in-cluster
frontend — one *in the sandbox's routing context* (it injects the routing key into every request
automatically), one against the baseline:

```bash
signadot local proxy --sandbox modal-route-dev --map http://frontend.hotrod.svc:8080@localhost:18080 > /root/proxy-sandbox.log 2>&1 &
signadot local proxy --cluster demo --map http://frontend.hotrod.svc:8080@localhost:18081 > /root/proxy-baseline.log 2>&1 &
```

Dispatch a ride through each (HotROD processes dispatches asynchronously — Kafka in between — so results
arrive on the notifications endpoint a few seconds later):

```bash
curl -s -X POST localhost:18080/dispatch -H "Content-Type: application/json" \
  -d '{"SessionID": 9001, "RequestID": 41, "PickupLocationID": 123, "DropoffLocationID": 1}'
curl -s -X POST localhost:18081/dispatch -H "Content-Type: application/json" \
  -d '{"SessionID": 9002, "RequestID": 42, "PickupLocationID": 123, "DropoffLocationID": 1}'

sleep 15
curl -s "localhost:18080/notifications?sessionID=9001&cursor=0" | jq -r '.notifications[] | .id + " | rk=" + .context.routingKey + " | " + .body'
curl -s "localhost:18081/notifications?sessionID=9002&cursor=0" | jq -r '.notifications[] | .id + " | rk=" + .context.routingKey + " | " + .body'
```

The sandboxed request comes back with the 2-minute ETA computed by the code Claude Code just changed,
running in this Modal sandbox:

```
req-41-location-resolve | rk=ug86wvt9f5nhq | Resolving locations
req-41-finding-driver | rk=ug86wvt9f5nhq | Finding an available driver
req-41-dispatched-driver | rk=ug86wvt9f5nhq | Driver T729782C arriving in 2m0s
```

The baseline request is untouched — random ETA, no routing key:

```
req-42-location-resolve | rk= | Resolving locations
req-42-finding-driver | rk= | Finding an available driver
req-42-route-resolve | rk= | Resolving routes
req-42-dispatched-driver | rk= | Driver T782962C arriving in 3m10s
```

Follow that first request's path: baseline frontend over HTTP → Kafka → baseline driver → gRPC call to
route, which — because the routing key rode along in baggage the whole way — was tunneled out of the
cluster into this Modal sandbox. One service overridden, per request; everything else shared.

The sandbox's preview endpoint gives the same isolation from anywhere, no proxies needed (send your API
key in the `signadot-api-key` header):

```bash
curl -s -X POST -H "signadot-api-key: $SIGNADOT_API_KEY" -H "Content-Type: application/json" \
  -d '{"SessionID": 8001, "RequestID": 31, "PickupLocationID": 123, "DropoffLocationID": 1}' \
  https://frontend--modal-route-dev.preview.signadot.com/dispatch
```

```
req-31-dispatched-driver | Driver T702029C arriving in 2m0s
```

## Cleanup

```bash
# inside the Modal sandbox
signadot sandbox delete modal-route-dev
```

```bash
# on your laptop
python3 -c "import modal; modal.Sandbox.from_id('sb-...').terminate()"
```

Modal sandboxes also self-terminate at the `timeout` set in the launcher (4 hours here), and the Signadot
sandbox expires via its `ttl` (1 day) — so nothing leaks if you just walk away.

## Production connectivity options

`ControlPlaneProxy` needs zero cluster exposure, which makes it perfect for getting started — but it is
rate-limited and adds latency, and Signadot recommends it only for setup and evaluation. For team-scale
use, switch the connection in `setup.sh` to one of:

- **PortForward** — the default for laptops. Requires a kubeconfig inside the Modal sandbox (deliver a
  [scoped ServiceAccount](https://www.signadot.com/docs/getting-started/installation/signadot-cli#configuration)
  kubeconfig as another Modal Secret) and a cluster API endpoint reachable from Modal's network:
  ```yaml
  local:
    connections:
    - cluster: staging
      type: PortForward
      kubeContext: staging
  ```
- **ProxyAddress** — a cluster admin exposes the Signadot Operator's SOCKS5 proxy on an address reachable
  from Modal (e.g., an internal LoadBalancer on a network Modal peers with):
  ```yaml
  local:
    connections:
    - cluster: staging
      type: ProxyAddress
      proxyAddress: socks5-signadot.my.company:1080
  ```

Both remove the ControlPlaneProxy latency, which also relaxes the `ROUTE_CALC_DELAY` workaround in Step 6.

## Headless automation

Everything above also works without an interactive shell — the same primitive that powers CI or
agent-orchestration use cases. From any Python process on your laptop:

```python
sb = modal.Sandbox.from_id("sb-...")
p = sb.exec("bash", "-lc",
    'cd /root/workspace/hotrod && claude -p "fix the failing ETA test" --allowedTools "Edit,Read,Bash"')
print(p.stdout.read())
```

## Troubleshooting

- **`409 Conflict: devbox ... is already claimed in session ...`** on `signadot local connect`: another
  environment (often your laptop) holds an active or stale local-connect session for your user. Run
  `signadot local disconnect` there, then retry in the Modal sandbox.
- **`couldn't read machine-id`**: `/etc/machine-id` is missing (gVisor). The provided `setup.sh` generates
  one; if you bypassed it, create the file manually.
- **`iptables ... exit status 1` / localnet errors**: you ran privileged `signadot local connect` under
  gVisor. Use `--unprivileged` — Modal sandboxes cannot do netfilter NAT.
- **Driver reports `DeadlineExceeded` and no final notification appears**: tunneled route calls exceeded
  HotROD's 1-second gRPC client timeout. Run route with `ROUTE_CALC_DELAY=1ms` (see Step 6), or move to a
  lower-latency connection type (see Production connectivity).
- **Proxies or the route service died unexpectedly**: avoid broad `pkill -f` patterns — `signadot local
  proxy` command lines contain your namespace and service names. Kill by port instead:
  `kill $(lsof -t -i :8083)`. If the connection itself dies, re-run
  `signadot local connect --unprivileged`; the sandboxes watcher re-attaches `modal-route-dev`
  automatically within seconds.
