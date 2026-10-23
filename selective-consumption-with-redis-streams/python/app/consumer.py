import pathlib
import socket

import requests

import platform_redis

from . import events
from .config import CONSUMER_GROUP, NOTIFIER_URL, PROCESSOR_VERSION, REDIS_URL, STREAM


def handle(entry_id, fields):
    message = {"id": fields.get("id", ""), "body": fields.get("body", "")}
    if PROCESSOR_VERSION == "v2":
        message["body"] = message["body"].upper()
    events.record(f"Consumed message from {STREAM} with processor {PROCESSOR_VERSION}: "
                  f"\"{message['body']}\"", message)
    # The requests instrumentation adds the entry's baggage (and routing key)
    # to this call.
    requests.post(f"{NOTIFIER_URL}/api/notify", json=message, timeout=10).raise_for_status()


def main():
    redis_client = platform_redis.Redis.from_url(REDIS_URL, decode_responses=True)
    consumer = platform_redis.StreamConsumer(
        redis_client, stream=STREAM, group=CONSUMER_GROUP, name=socket.gethostname(),
        on_ready=lambda: pathlib.Path("/tmp/ready").touch())
    consumer.run(handle)
