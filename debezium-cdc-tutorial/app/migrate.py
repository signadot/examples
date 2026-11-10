"""Creates the schema. Runs once, as a Kubernetes Job."""

import sqlalchemy
from sqlalchemy import text

import platform_cdc

from .config import DATABASE_URL


def main():
    engine = sqlalchemy.create_engine(DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS orders (
                id     text PRIMARY KEY,
                item   text NOT NULL,
                status text NOT NULL
            )"""))
        # The one Signadot-related line: have Postgres stamp each row of the
        # table Debezium captures with the context of the request that wrote it.
        platform_cdc.track_table(conn, "orders")
        # For the demo's event log; Debezium doesn't capture this table.
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS event_log (
                id    bigserial PRIMARY KEY,
                event text NOT NULL
            )"""))
