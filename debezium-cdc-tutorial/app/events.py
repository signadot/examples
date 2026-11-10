"""Event log that shows which workload handled each step of an order.

This is only for the demo. It reads the Signadot routing key and sandbox name
purely to display them.
"""

import json
import logging
import os
from datetime import datetime, timezone

import sqlalchemy
from opentelemetry import baggage
from sqlalchemy import text

from .config import DATABASE_URL

log = logging.getLogger("events")
_engine = sqlalchemy.create_engine(DATABASE_URL)


def record(order_id, entry):
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "logEntry": entry,
        "context": {
            "baselineWorkload": os.getenv("SIGNADOT_BASELINE_NAME", ""),
            "routingKey": baggage.get_baggage("sd-routing-key") or "",
            "sandboxName": os.getenv("SIGNADOT_SANDBOX_NAME", ""),
            "orderID": order_id,
        },
    }
    log.info("%s: %s", entry, json.dumps(event["context"]))
    with _engine.begin() as conn:
        conn.execute(text("INSERT INTO event_log (event) VALUES (:event)"),
                     {"event": json.dumps(event)})


def read(cursor):
    # Events after the cursor (an event_log id), or all of them for cursor 0.
    with _engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, event FROM event_log WHERE id > :cursor ORDER BY id LIMIT 500"),
            {"cursor": cursor}).all()
    return [json.loads(event) for _, event in rows], (rows[-1][0] if rows else cursor)
