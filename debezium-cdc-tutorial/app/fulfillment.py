import pathlib

import requests

import platform_cdc

from . import events
from .config import CONSUMER_GROUP, FULFILLMENT_VERSION, KAFKA_BROKERS, NOTIFIER_URL, ORDERS_TOPIC


def handle(change):
    order = change.row
    item = order["item"].upper() if FULFILLMENT_VERSION == "v2" else order["item"]
    text = f"order {order['id']} ({item}) is {order['status']}"
    events.record(order["id"], f"Consumed change event (op {change.op}) with fulfillment "
                               f"{FULFILLMENT_VERSION}: \"{text}\"")
    # The requests instrumentation adds the change event's baggage (and
    # routing key) to this call.
    requests.post(f"{NOTIFIER_URL}/api/notify", json={"id": order["id"], "text": text},
                  timeout=10).raise_for_status()


def main():
    consumer = platform_cdc.ChangeConsumer(
        KAFKA_BROKERS, topic=ORDERS_TOPIC, group=CONSUMER_GROUP,
        on_ready=lambda: pathlib.Path("/tmp/ready").touch())
    consumer.run(handle)
