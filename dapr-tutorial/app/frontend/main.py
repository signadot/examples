"""
frontend: a tiny web UI. Every API call goes through the local Dapr sidecar to
another app, forwarding the Signadot routing headers the browser sent (set by a
Signadot preview URL or the browser extension).
"""
import os

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from common import dapr
from signadot import routing

CHECKOUT = os.environ.get("CHECKOUT_APP", "checkout")
ORDER_PROCESSOR = os.environ.get("ORDER_PROCESSOR_APP", "order-processor")

app = FastAPI()


@app.post("/api/orders")
async def place_order(order: dict, request: Request):
    resp = await dapr.invoke(CHECKOUT, "orders", verb="POST", json=order, headers=routing.routing_headers(request.headers))
    return _passthrough(resp, routing_key=routing.routing_key(request.headers))


@app.get("/api/processed")
async def processed(request: Request):
    resp = await dapr.invoke(ORDER_PROCESSOR, "processed", headers=routing.routing_headers(request.headers))
    return _passthrough(resp, routing_key=routing.routing_key(request.headers))


def _passthrough(resp, **extra) -> JSONResponse:
    """Relay the callee's answer, adding the routing key this request carried."""
    if resp.headers.get("content-type", "").startswith("application/json"):
        body = resp.json()
        content = {"routing_key": extra.get("routing_key"), "result": body}
    else:
        content = {"routing_key": extra.get("routing_key"), "error": resp.text}
    return JSONResponse(status_code=resp.status_code, content=content)


@app.get("/", response_class=HTMLResponse)
async def index():
    return INDEX_HTML


INDEX_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>Dapr + Signadot demo</title>
<style>
  body { font: 15px/1.4 system-ui, sans-serif; max-width: 720px; margin: 2rem auto; padding: 0 1rem; color: #222; }
  input, button { font: inherit; padding: .4rem .6rem; }
  pre { background: #f4f4f4; padding: .75rem; overflow-x: auto; }
  table { border-collapse: collapse; width: 100%; } td, th { border-bottom: 1px solid #ddd; padding: .35rem .5rem; text-align: left; }
  .muted { color: #666; }
</style></head>
<body>
<h1>Dapr + Signadot demo</h1>
<p class="muted">Requests carry a Signadot routing key when opened through a preview URL or with the browser extension.
Compare <b>handled_by</b> and <b>processed_by</b> with and without one.</p>

<h2>1. Place an order (service invocation: frontend &rarr; checkout)</h2>
<form id="f"><input id="item" value="coffee" /> <button>Place order</button></form>
<pre id="out">(no order yet)</pre>

<h2>2. Processed orders (pub/sub: checkout &rarr; order-processor)</h2>
<p class="muted">Fetched from order-processor every 2s via service invocation. Routing key on this page: <code id="rk">-</code></p>
<table><thead><tr><th>id</th><th>item</th><th>created_by</th><th>processed_by</th><th>routing_key</th></tr></thead><tbody id="rows"></tbody></table>

<script>
document.getElementById('f').onsubmit = async (e) => {
  e.preventDefault();
  const r = await fetch('/api/orders', {method: 'POST', headers: {'content-type': 'application/json'},
                                      body: JSON.stringify({item: document.getElementById('item').value})});
  document.getElementById('out').textContent = JSON.stringify(await r.json(), null, 2);
};
async function refresh() {
  const r = await fetch('/api/processed');
  const body = await r.json();
  document.getElementById('rk').textContent = body.routing_key || '(none: baseline)';
  const rows = Array.isArray(body.result) ? body.result : [];
  document.getElementById('rows').innerHTML = rows.slice().reverse().map(o =>
    `<tr><td>${o.id}</td><td>${o.item}</td><td>${o.created_by}</td><td>${o.processed_by}</td><td>${o.routing_key || ''}</td></tr>`).join('');
}
refresh(); setInterval(refresh, 2000);
</script>
</body></html>
"""
