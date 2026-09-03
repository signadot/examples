"""
checkout: receives orders (via Dapr service invocation) and publishes an
`order.created` event (via Dapr pub/sub).

Use case 1 ends here: whichever checkout instance answers, baseline or sandbox
fork, reports itself in the response.
Use case 2 starts here: the routing context is placed on the message so the
right order-processor instance picks it up.
"""
import logging
import os
import uuid

from fastapi import FastAPI, Request

from common import dapr
from signadot import routing

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # one line per Dapr call is too chatty
log = logging.getLogger("checkout")

PUBSUB = os.environ.get("PUBSUB_NAME", "pubsub")
TOPIC = os.environ.get("ORDERS_TOPIC", "orders")
POD = os.environ.get("HOSTNAME", "unknown")

app = FastAPI()


@app.post("/orders")
async def create_order(order: dict, request: Request):
    order_id = uuid.uuid4().hex[:8]
    me = await dapr.app_id()

    event = {
        "specversion": "1.0",
        "id": order_id,
        "type": "order.created",
        "source": me,
        "datacontenttype": "application/json",
        "data": {"id": order_id, "item": order.get("item", "?"), "created_by": me},
    }
    # Carry the Signadot routing context inside the message as a CloudEvents
    # extension attribute. Dapr passes unknown attributes through untouched,
    # so this works with any broker (Redis Streams, Kafka, ...).
    baggage = request.headers.get("baggage")
    if baggage:
        event["baggage"] = baggage

    await dapr.publish(PUBSUB, TOPIC, event)
    log.info("published order %s routing_key=%s", order_id, routing.routing_key(request.headers))
    return {"order_id": order_id, "handled_by": {"app_id": me, "pod": POD}}


@app.get("/healthz")
async def healthz():
    return {"ok": True}
