"""
order-processor: subscribes to the `orders` topic through Dapr pub/sub and
decides, per message, whether this instance should act on it.

The baseline and every sandbox fork receive every message, because each Dapr
app-id is its own consumer group. The Signadot Routes API decides who acts.
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from common import dapr
from signadot import routing
from signadot.routes_api import RoutesClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # one line per Dapr call is too chatty
log = logging.getLogger("order-processor")

PUBSUB = os.environ.get("PUBSUB_NAME", "pubsub")
TOPIC = os.environ.get("ORDERS_TOPIC", "orders")
POD = os.environ.get("HOSTNAME", "unknown")

routes = RoutesClient.from_env()
processed: list = []  # in-memory and per instance: enough for a demo


@asynccontextmanager
async def lifespan(_: FastAPI):
    poller = asyncio.create_task(routes.run())
    yield
    poller.cancel()


app = FastAPI(lifespan=lifespan)


@app.get("/dapr/subscribe")
async def subscribe():
    """Programmatic subscription: the sidecar asks us what to subscribe to.

    Because it lives in code, a sandbox fork (which runs under a different
    app-id) subscribes automatically. A declarative Subscription CRD scoped to
    the baseline app-id would NOT apply to the fork.
    """
    return [{"pubsubname": PUBSUB, "topic": TOPIC, "route": "/orders"}]


@app.post("/orders")
async def on_order(event: dict, request: Request):
    order = event.get("data") or {}
    key = routing.routing_key_from_event(event, request.headers)

    if not routes.should_process(key):
        log.info("skip order %s routing_key=%s (%s)", order.get("id"), key, routes.identity)
        return {"status": "SUCCESS"}  # ack without acting: it belongs to another instance

    record = {**order, "routing_key": key, "processed_by": await dapr.app_id(), "pod": POD}
    processed.append(record)
    log.info("processed order %s routing_key=%s (%s)", order.get("id"), key, routes.identity)
    return {"status": "SUCCESS"}


@app.get("/processed")
async def list_processed():
    return processed[-20:]
