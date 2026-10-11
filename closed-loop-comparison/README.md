# closed-loop-comparison

A harness for comparing Claude Code behavior **with** vs **without** [Signadot agent-skills](https://github.com/signadot/agent-skills), using [Docker Sandboxes](https://docs.docker.com/ai/sandboxes/get-started/) (`sbx`) as the execution environment.

Each run clones the target repo (default: [hotrod](https://github.com/signadot/hotrod)) onto the **host** at `./<sandbox-name>/<repo>/`, creates a sandbox with that directory mounted read-write as its project root, and drops you into `claude` so you can run the same prompt under both conditions and compare outcomes. The clone is persistent on the host — edit with host tools, survives sandbox rebuilds.

## Prerequisites

- The [`sbx` CLI](https://docs.docker.com/ai/sandboxes/get-started/), installed and logged in (`sbx login`)
- `git`
- For `--with-skill`: a Signadot account, an API key, and a cluster connected to that org with the target app (e.g. HotROD) deployed

The script adds `sbx` network allow rules for `*.signadot.com`, in-cluster DNS suffixes (`*.svc`, `*.svc.cluster`, `*.svc.cluster.local`), and the Playwright download hosts. Run `sbx policy ls` to review them.

## Modes

### `--without-skill` (baseline)
Vanilla Claude Code in a sandbox with the target repo cloned. No signadot tooling.

```sh
./sbx-run.sh --without-skill
./sbx-run.sh --without-skill --repo https://github.com/some/other-repo
```

### `--with-skill` (signadot-augmented)
Same as baseline, plus:
- mounts `./agent-skills` read-write into the sandbox and symlinks `~/.claude/skills` to it (edits from inside propagate back to the host)
- installs the `signadot` CLI
- writes `~/.signadot/config.yaml` for `SIGNADOT_ORG` / `SIGNADOT_CLUSTER` and logs in with `SIGNADOT_API_KEY` (all three required in env)
- registers the signadot MCP server with `claude`
- installs Playwright (Chromium + MCP server) and `grpcurl` for validation
- installs a `SessionStart` hook that auto-runs `signadot local connect` on every session

```sh
export SIGNADOT_API_KEY=...
export SIGNADOT_ORG=my-org
export SIGNADOT_CLUSTER=my-cluster
./sbx-run.sh --with-skill
./sbx-run.sh --with-skill --repo https://github.com/some/other-repo
```

## Config (env vars)

| Var | Default | Purpose |
| --- | --- | --- |
| `REPO_URL` | `https://github.com/signadot/hotrod` | Target repo cloned on the host at `./<sandbox-name>/<basename>` and mounted as the sandbox project root |
| `SBX_NAME` | `sbx-with-env` / `sbx-without-env` | Sandbox name (also the host directory name containing the repo); `--name` overrides it |
| `SIGNADOT_API_KEY` | — | Signadot API key (required for `--with-skill`) |
| `SIGNADOT_ORG` | — | Signadot org name (required for `--with-skill`) |
| `SIGNADOT_CLUSTER` | — | Cluster name used for `signadot local connect` (required for `--with-skill`) |
| `SKILLS_SRC` | `$PWD/agent-skills` | Host path for the agent-skills checkout |
| `SKILLS_REPO` | `https://github.com/signadot/agent-skills` | Where to clone skills from if missing |

## Prompts

[`prompts/HOTROD.md`](prompts/HOTROD.md) holds the prompts used for comparisons. Prompts 1–3 target HotROD; 4–6 target [microservices-demo](https://github.com/GoogleCloudPlatform/microservices-demo) (`--repo https://github.com/GoogleCloudPlatform/microservices-demo`).

Where a prompt has two variants, use the first for the baseline run and the second (which invokes `/signadot-validate`) for the `--with-skill` run. For the other prompts, append the line under **With Signadot** in `--with-skill` runs. "The demo cluster" means whatever cluster `SIGNADOT_CLUSTER` points at.
