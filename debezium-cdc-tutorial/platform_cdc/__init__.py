"""Change data capture helpers a platform team ships so app code works in Signadot sandboxes.

- create_engine: a sqlalchemy.create_engine whose transactions carry the
  OpenTelemetry context (and with it the Signadot routing key) into Postgres.
- track_table: a one-time migration step that makes Postgres stamp that
  context on every row written to a table, where Debezium picks it up.
- ChangeConsumer: reads a Debezium topic and hands the app only the change
  events meant for this workload (baseline or sandbox).

Routing is on in sandboxes and in workloads that set SIGNADOT_BASELINE_NAME
(and SIGNADOT_BASELINE_NAMESPACE); elsewhere, such as a cluster without
Signadot, ChangeConsumer processes every change event.
"""

from .consumer import Change, ChangeConsumer
from .db import create_engine, track_table

__all__ = ["Change", "ChangeConsumer", "create_engine", "track_table"]
