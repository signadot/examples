# Cloud Dev Environment: Modal Sandbox + Signadot

You are running inside an ephemeral Modal Sandbox that acts as this developer's
"local" environment. It is connected to a shared Kubernetes staging cluster via
`signadot local connect --unprivileged` (ControlPlaneProxy). There is no cluster
DNS here — reach in-cluster services through `signadot local proxy` port
mappings on localhost.

## The workflow

1. The HotROD demo app runs as the baseline in the cluster.
2. The service under development is `route` (Go gRPC service, listens on :8083),
   cloned at `/root/workspace/hotrod`.
3. A Signadot sandbox (`/root/workspace/local-route.yaml`) maps the in-cluster
   route Deployment to `localhost:8083` here. Requests carrying the sandbox
   routing key are served by THIS environment; all other traffic hits baseline.
   Apply it with:
   `signadot sandbox apply -f /root/workspace/local-route.yaml --set cluster=<cluster> --set namespace=<ns>`
4. Run the route service:
   `cd /root/workspace/hotrod && ROUTE_CALC_DELAY=1ms go run ./cmd/hotrod/main.go route > /root/route.log 2>&1 &`
   (`ROUTE_CALC_DELAY=1ms` keeps each call inside the driver service's 1-second
   gRPC client timeout — tunneled calls already carry extra latency.)
5. Start proxies to reach the in-cluster frontend:
   - Sandboxed context (auto-injects the routing key):
     `signadot local proxy --sandbox modal-route-dev --map http://frontend.<ns>.svc:8080@localhost:18080 > /root/proxy-sandbox.log 2>&1 &`
   - Baseline context (no routing key):
     `signadot local proxy --cluster <cluster> --map http://frontend.<ns>.svc:8080@localhost:18081 > /root/proxy-baseline.log 2>&1 &`
6. Test end to end (dispatch is async; results arrive on /notifications):
   `curl -s -X POST localhost:18080/dispatch -H "Content-Type: application/json" -d '{"SessionID": 1001, "RequestID": 1, "PickupLocationID": 123, "DropoffLocationID": 1}'`
   then after ~10s:
   `curl -s "localhost:18080/notifications?sessionID=1001&cursor=0" | jq -r '.notifications[].body'`
   Compare against the same requests on the baseline proxy (localhost:18081).

## Rules

- Never print or commit the values of SIGNADOT_API_KEY, CLAUDE_CODE_OAUTH_TOKEN,
  or ANTHROPIC_API_KEY.
- Baseline behavior (requests without the routing key) must remain unaffected.
- Do not kill processes with broad patterns like `pkill -f hotrod` — that
  matches the signadot proxies too (their args contain the namespace). Kill by
  port instead: `kill $(lsof -t -i :8083)`.
