# Modal Sandboxes + Signadot: Agent-Driven Development Against a Shared Cluster

Run Claude Code, the Signadot CLI, and a service under development inside an ephemeral [Modal Sandbox](https://modal.com/docs/guide/sandbox), connected to a shared Kubernetes cluster through Signadot. Request-tagged traffic from the cluster routes into the Modal sandbox; baseline traffic is untouched. Your laptop is a thin client (`modal shell`); the dev environment is disposable cloud infrastructure.

**Guided walkthrough:** [Closed-Loop Development with Claude Code in Modal Sandboxes](https://www.signadot.com/docs/tutorials/closed-loop-modal-sandboxes) in the Signadot docs. This README is the runnable reference.

## Quick start

Prerequisites: a cluster with the [Signadot Operator](https://www.signadot.com/docs/installation/signadot-operator), a [Signadot API key](https://www.signadot.com/) (from Settings > Service Accounts > your service account > Keys), a [Modal](https://modal.com/) account with the CLI (`pip install modal && modal setup`), and Claude Code auth (`claude setup-token` or an Anthropic API key).

```sh
# Credentials enter the sandbox only as Modal Secrets
modal secret create signadot-credentials SIGNADOT_ORG=<org> SIGNADOT_API_KEY=<key>
modal secret create claude-code-auth CLAUDE_CODE_OAUTH_TOKEN=<token>   # or ANTHROPIC_API_KEY=<key>

# Launch the sandbox (first run builds the image), then shell in
modal run launch_sandbox.py --cluster <cluster-name>
modal shell <sandbox-id-printed-by-the-launcher>
```

The launcher bakes Go, Node, Claude Code, and the Signadot CLI into the image and runs `in-sandbox/setup.sh`, which configures the CLI (ControlPlaneProxy: API key only, no kubeconfig) and starts `signadot local connect --unprivileged`. From there, follow the [docs tutorial](https://www.signadot.com/docs/tutorials/closed-loop-modal-sandboxes) for the full workflow: apply the sandbox spec, let Claude Code make a change, and verify tagged traffic reaching the modified service while baseline stays untouched.

## What's in this repo

| File | Purpose |
|---|---|
| `launch_sandbox.py` | Modal image definition + sandbox launcher (4-hour session timeout) |
| `in-sandbox/setup.sh` | Signadot CLI config + Local Connect, run at sandbox start |
| `in-sandbox/CLAUDE.md` | Context for Claude Code inside the sandbox |
| `local-route.yaml` | Signadot sandbox spec mapping the in-cluster `route` Deployment to `localhost:8083` in the Modal sandbox |

## Architecture

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
    Dev["Developer laptop<br/>(modal shell: thin client)"]
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

HotROD's request flow makes this a strong test of routing-context propagation: the tagged request crosses HTTP, Kafka, and gRPC before reaching the sandboxed service.

## Adapting to your stack

Your service's language does not matter; only two files carry customization:

1. `launch_sandbox.py`: the image installs the Go toolchain because HotROD is Go. Swap in your runtime's toolchain; Claude Code and the Signadot CLI stay.
2. `local-route.yaml`: point the fork at your own service's Deployment, namespace, and port.

## Notes

- Modal sandboxes self-terminate at the launcher's `timeout` (4 hours here); the Signadot sandbox and Local Connect die with them.
- ControlPlaneProxy connectivity is rate-limited and intended for setup and evaluation. For production use, see the connectivity options in the [docs tutorial](https://www.signadot.com/docs/tutorials/closed-loop-modal-sandboxes).
- Troubleshooting (machine-id, iptables/unprivileged mode, timeouts, process cleanup) is covered in the docs tutorial.
