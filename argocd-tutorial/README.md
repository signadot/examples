# Test Coding Agent Pull Requests with Argo CD and Signadot

> **Step-by-step tutorial:** [Test Coding Agent Pull Requests with Argo CD and Signadot](https://www.signadot.com/docs/tutorials/argocd-coding-agent-pull-requests?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=argocd)
> explains how this example works. The [Argo CD integration guide](https://www.signadot.com/docs/guides/integrate-ci/argocd?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=argocd)
> is the reference, and [ArgoCD preview environments](https://www.signadot.com/articles/argocd-preview-environments/?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=argocd)
> compares the ApplicationSet pattern with routed previews.

A coding agent opens a pull request on [HotROD](https://github.com/signadot/hotrod). An Argo CD
ApplicationSet turns the PR into an Application whose hooks create a
[Signadot sandbox](https://www.signadot.com/docs/concepts/sandbox) that runs the PR's `route`
image, run HotROD's Playwright suite from the PR against it, and delete the sandbox when the PR
closes. Argo CD Notifications reports the result on the PR as the `argocd/preview` check. When the
check fails, the agent reads why through the read-only
[Argo CD MCP server](https://github.com/argoproj-labs/mcp-for-argocd), pushes a fix, and repeats
until the check passes. It needs no kubeconfig and no Signadot API key: it pushes to Git and reads
Argo CD.

```
argocd/config.yaml     read-only "agent" account, RBAC, commit-status notifications
argocd/hotrod.yaml     the baseline: HotROD from your fork's main branch
argocd/previews.yaml   AppProject and ApplicationSet: one Application per PR labeled "preview"
preview/               the chart each PR's Application renders: sandbox spec and three hook Jobs
hotrod/                files for your HotROD fork: image workflow, MCP config, agent instructions
prompt.md              the task you give the agent
```

## Before you begin

- A Kubernetes cluster with the [Signadot Operator](https://www.signadot.com/docs/installation/signadot-operator)
  installed. Docker Desktop, kind or minikube works.
- The [Signadot CLI](https://www.signadot.com/docs/getting-started/installation/signadot-cli),
  logged in, with a local connection for the cluster in `~/.signadot/config.yaml`:

  ```yaml
  local:
    connections:
      - cluster: <your-signadot-cluster>
        kubeContext: <your-kube-context>
        type: PortForward
  ```

- A Signadot API key, and the `argocd`, `gh` and `kubectl` CLIs, Node.js (for `npx`), and
  [Claude Code](https://code.claude.com) or another agent that supports MCP.

Tested with Argo CD v3.5.6, argocd-mcp 0.9.0, Signadot CLI v1.9.0, Operator 1.4.0 and Claude
Code 2.1 on Docker Desktop (October 2026).

## 1. Fork HotROD and add the preview files

```bash
export OWNER=<your-github-user>   # lowercase
git clone https://github.com/signadot/examples.git
gh repo fork signadot/hotrod --clone
cd hotrod
gh repo set-default $OWNER/hotrod   # otherwise gh, and the agent, target signadot/hotrod
cp -R ../examples/argocd-tutorial/hotrod/. .
git rm -q .github/workflows/build.yml   # upstream CI, needs Signadot's own secrets
git add -A && git commit -m "Add Argo CD previews" && git push origin main
gh label create preview
```

Open your fork's **Actions** tab and enable workflows; GitHub disables them on new forks.

## 2. Install Argo CD and add two secrets

```bash
kubectl create namespace argocd
kubectl apply -n argocd --server-side --force-conflicts \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/v3.5.6/manifests/install.yaml

kubectl create namespace hotrod-previews
kubectl -n hotrod-previews create secret generic signadot \
  --from-literal=SIGNADOT_ORG=<your-org> --from-literal=SIGNADOT_API_KEY=<your-api-key>
kubectl -n argocd patch secret argocd-notifications-secret \
  -p '{"stringData": {"github-token": "<your-github-token>"}}'
```

Only the hook Jobs in `hotrod-previews` get the Signadot key, and never the containers that run
the PR's code. The GitHub token lets the ApplicationSet list your PRs and Argo CD Notifications set
commit statuses. Create a fine-grained token for your fork with **Commit statuses: Read and write**
and **Pull requests: Read**.

## 3. Point Argo CD at your fork

```bash
export CLUSTER=<your-signadot-cluster>
cd ../examples/argocd-tutorial
sed -i.orig -e "s/<owner>/$OWNER/g" -e "s/<cluster>/$CLUSTER/g" argocd/*.yaml
kubectl apply --server-side --field-manager=argocd-tutorial -f argocd/
kubectl -n argocd get applications
```

The separate field manager adds the agent account and notification settings without removing the
defaults the install put in `argocd-cm`. After a minute, `hotrod` is `Synced` and `Healthy`. If
HotROD already runs in the `hotrod` namespace, Argo CD adopts it.

The `preview` label is the gate: anyone who can add it to a PR gets that PR's code and tests run in
your cluster. The ApplicationSet renders the chart from this repository's `main` branch; for your
own services, keep the chart in a repository your platform team controls, not in the app repo the
agent pushes to, and pin `targetRevision`.

## 4. Give the agent read-only access to Argo CD

```bash
signadot local connect
argocd login argocd-server.argocd.svc --insecure --username admin \
  --password "$(argocd admin initial-password -n argocd | head -1)"
export ARGOCD_API_TOKEN=$(argocd account generate-token --account agent --expires-in 24h)
argocd logout argocd-server.argocd.svc --insecure
```

`signadot local connect` makes in-cluster addresses such as `argocd-server.argocd.svc` resolve on
your machine; the Argo CD UI is at <https://argocd-server.argocd.svc>. The `agent` account can
read Applications in the `previews` project and their logs, nothing else. Logging out keeps your
admin session out of the agent's shell.

Argo CD's certificate is self-signed here, so `--insecure` and `NODE_TLS_REJECT_UNAUTHORIZED=0` in
`.mcp.json` skip verification. Drop both once Argo CD has a trusted certificate.

## 5. Hand the agent the task

```bash
cd ../../hotrod
claude
```

Approve the `argocd` MCP server from `.mcp.json`, then paste [`prompt.md`](prompt.md):

> In the route service, make the "Resolving routes" notification show the ETA that route computed,
> for example "Resolving routes (ETA 12m30s)". Open a pull request for it and don't stop until its
> preview passes. Then tell me the PR URL, the preview URL and what you checked.

`AGENTS.md` (loaded through `CLAUDE.md`) tells the agent how previews work and which MCP tools to
use when one fails. `.claude/settings.json` denies Claude Code `kubectl`, `argocd` and `signadot`,
so the preview is its only way to test.

The first image build creates the package `ghcr.io/<owner>/hotrod`. If GitHub makes it private, the
sandbox Job keeps logging `DENIED` after the `Preview image` run succeeds. HotROD is open source, so
make the package public in its **Package settings**, and the preview continues on its own. Keep
images of your own services private, and give the forks and `wait-for-image` pull credentials.

## 6. What happens

In our run, Claude Code found the notification in `services/route/server.go` and the Playwright
test that asserts its text, changed both, and opened the PR with the `preview` label. It then
waited on `gh pr checks --watch`:

- The `Preview image` run pushed `ghcr.io/<owner>/hotrod:<head sha>` in under two minutes.
- Argo CD created `hotrod-pr-<number>`. Its Sync hook created sandbox `hotrod-pr-<number>`, which
  runs that image in place of `route`, and its PostSync hook ran the PR's Playwright suite with the
  sandbox's routing key.
- About two and a half minutes after the push, `argocd/preview` turned green.

The agent read the e2e Job's log with `get_application_workload_logs` to confirm the run tested
its commit, and added the preview URL to the PR description.

## 7. Watch the agent fix a failing preview

`driver` gives each `route` call a one-second deadline (`services/route/client.go`). Once the agent
is done, act as a teammate: in a second terminal, in `hotrod` with the agent's branch checked out,
push a commit that makes `route` slower than that:

```bash
perl -pi -e 's/50 \* time\.Millisecond/1500 * time.Millisecond/' pkg/config/route.go
git commit -am "route: simulate a slower routing engine" && git push
```

It builds and passes unit tests, but in the preview no ride gets a driver and both Playwright tests
fail. Tell the agent:

> The argocd/preview check on <PR URL> has been failing since a teammate pushed a commit to your
> branch. Find out why, fix it, and don't stop until the preview passes.

In our run it read the failure through `get_application` and `get_application_workload_logs`,
traced it to the one-second timeout, and reverted the commit. The check passed less than two
minutes after its push. It also explained why raising the timeout would not help: the timeout runs
in `driver`, which the preview doesn't fork.

## 8. Review and clean up

Open the preview URL from the PR's `argocd/preview` check while signed in to Signadot, request a
ride, and look for the ETA in the `route` notification.

Merge or close the PR. Within a minute the ApplicationSet deletes `hotrod-pr-<number>`, its
PostDelete hook deletes the sandbox, and `signadot sandbox list` no longer shows it.

To remove the setup, close any open `preview` PRs first so their hooks can delete their sandboxes.
Then, from `examples/argocd-tutorial`, run the following. HotROD keeps running in `hotrod`.

```bash
kubectl delete -f argocd/
kubectl delete namespace hotrod-previews argocd
```

## Troubleshooting

- **The sandbox Job keeps logging `waiting for CI to push ...`.** With `MANIFEST_UNKNOWN`, the
  image isn't there yet: check that Actions is enabled in your fork and that the `Preview image`
  run succeeded. With `DENIED` after a successful run, the package is private; make it public.
- **The PR gets no `argocd/preview` check.** The PR needs the `preview` label, and the GitHub
  token needs commit status access to your fork. `kubectl -n argocd logs deploy/argocd-notifications-controller`
  shows the GitHub API's answer.
- **`get_application_workload_logs` returns `[]`.** Argo CD only reads logs from Pods it shows
  under the Job, and it hides kinds the AppProject doesn't list. Keep `Pod` in the `previews`
  project.
- **The agent's MCP calls fail with 401.** The token from step 4 expires after 24 hours. Generate a
  new one and restart the agent.
