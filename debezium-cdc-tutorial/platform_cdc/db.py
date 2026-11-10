"""Carry the OpenTelemetry context from a request into the rows it writes.

A change event is produced by Debezium, not by the service that handled the
request, so the request's context has to be stored with the row for Debezium
to find it. The app never sees this: the engine tells Postgres the context of
each transaction, and a trigger copies it into two columns of every row the
transaction inserts or updates.
"""

import re

import sqlalchemy
from opentelemetry import propagate
from sqlalchemy import event, text

# Debezium moves these columns into the Kafka headers "traceparent" and
# "baggage" (see debezium/orders-connector.json).
TRACEPARENT_COLUMN = "otel_traceparent"
BAGGAGE_COLUMN = "otel_baggage"

_STAMP_FUNCTION = f"""
CREATE OR REPLACE FUNCTION otel_stamp_context() RETURNS trigger AS $$
BEGIN
  -- A write outside a request, or by a client that doesn't use the platform
  -- engine, has no context: the columns are cleared, so the change event
  -- carries no routing key and goes to the baseline.
  NEW.{TRACEPARENT_COLUMN} := NULLIF(current_setting('otel.traceparent', true), '');
  NEW.{BAGGAGE_COLUMN} := NULLIF(current_setting('otel.baggage', true), '');
  RETURN NEW;
END
$$ LANGUAGE plpgsql
"""


def create_engine(url, **kwargs):
    """sqlalchemy.create_engine, plus the OpenTelemetry context on every transaction."""
    engine = sqlalchemy.create_engine(url, **kwargs)

    @event.listens_for(engine, "begin")
    def set_context(conn):
        carrier = {}
        propagate.inject(carrier)
        if not carrier:
            return
        # Transaction-local settings (is_local = true): they vanish at commit
        # or rollback, so a pooled connection never leaks one request's
        # context into the next.
        conn.exec_driver_sql(
            "SELECT set_config('otel.traceparent', %s, true), set_config('otel.baggage', %s, true)",
            (carrier.get("traceparent", ""), carrier.get("baggage", "")))

    return engine


def track_table(conn, table):
    """Make Postgres stamp the writer's context on each row of a table. Run it in a migration."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", table):
        raise ValueError(f"invalid table name: {table}")
    conn.execute(text(_STAMP_FUNCTION))
    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {TRACEPARENT_COLUMN} text, "
                      f"ADD COLUMN IF NOT EXISTS {BAGGAGE_COLUMN} text"))
    conn.execute(text(f"CREATE OR REPLACE TRIGGER otel_stamp_context BEFORE INSERT OR UPDATE "
                      f"ON {table} FOR EACH ROW EXECUTE FUNCTION otel_stamp_context()"))
