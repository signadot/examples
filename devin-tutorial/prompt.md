In ~/repos/hotrod, change the route service so that every computed ETA is
exactly 2 minutes (services/route/server.go). Keep the FAST_ROUTE override
and the rounding logic intact. Smallest possible diff.

Before you report back, validate the change end to end against the shared
cluster with Signadot (see the `signadot` knowledge for commands):

1. Connect this VM to the cluster with `signadot local connect`.
2. Run your modified route service locally on port 8083.
3. Use the Signadot MCP to create a sandbox named `devin-route-eta` in
   cluster `my-cluster` that maps Deployment `route` in namespace `hotrod` to
   localhost:8083 on this VM's devbox. I approve that spec; no need to ask.
4. Run HotROD's Playwright e2e suite against the sandbox as a Signadot Job
   and wait for it to finish. If it fails, find out why, fix it, and rerun.
5. Prove the behavior change: dispatch one ride with the sandbox routing key
   and one without (baseline), then compare the driver notifications.

Report the diff, the sandbox routing key, the job name and result, and the
two notifications. Leave the sandbox and the route service running.
