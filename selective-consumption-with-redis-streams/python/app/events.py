"""Event log that the demo UI polls to show which workload handled each step.

This is only for the demo's UI. It reads the Signadot routing key and sandbox
name purely to display them.
"""

import json
import logging
import os
from datetime import datetime, timezone

import redis
from opentelemetry import baggage

from .config import REDIS_URL

EVENT_LOG = "demo:event-log"

log = logging.getLogger("events")
_redis = redis.Redis.from_url(REDIS_URL, decode_responses=True)


def record(text, message):
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "logEntry": text,
        "context": {
            "baselineWorkload": {
                "namespace": os.getenv("SIGNADOT_BASELINE_NAMESPACE", ""),
                "name": os.getenv("SIGNADOT_BASELINE_NAME", ""),
            },
            "routingKey": baggage.get_baggage("sd-routing-key") or "",
            "sandboxName": os.getenv("SIGNADOT_SANDBOX_NAME", ""),
            "message": message,
        },
    }
    log.info("%s: %s", text, json.dumps(event["context"]))
    _redis.xadd(EVENT_LOG, {"event": json.dumps(event)}, maxlen=1000, approximate=True)


def read(cursor):
    # Entries after the cursor (an entry ID), or all of them for cursor "0".
    start = "-" if cursor in ("", "0") else f"({cursor}"
    entries = _redis.xrange(EVENT_LOG, min=start, max="+", count=500)
    events = [json.loads(fields["event"]) for _, fields in entries]
    return events, (entries[-1][0] if entries else cursor)
