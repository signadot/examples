from flask import Flask, request
from sqlalchemy import text

import platform_cdc

from . import events
from .config import DATABASE_URL

# platform_cdc.create_engine is sqlalchemy.create_engine plus the
# OpenTelemetry context on every transaction.
engine = platform_cdc.create_engine(DATABASE_URL)


def create_app():
    app = Flask(__name__)

    @app.get("/healthz")
    def healthz():
        return "ok"

    @app.post("/api/orders")
    def create_order():
        order = request.get_json()
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO orders (id, item, status) VALUES (:id, :item, 'new')"),
                         {"id": order["id"], "item": order["item"]})
        events.record(order["id"], "Inserted order into Postgres")
        return {"id": order["id"]}, 201

    @app.post("/api/orders/<order_id>/ship")
    def ship_order(order_id):
        with engine.begin() as conn:
            found = conn.execute(text("UPDATE orders SET status = 'shipped' WHERE id = :id"),
                                 {"id": order_id}).rowcount
        if not found:
            return {"error": "no such order"}, 404
        events.record(order_id, "Updated order in Postgres")
        return {"id": order_id}

    @app.get("/api/events")
    def list_events():
        found, cursor = events.read(request.args.get("cursor", 0, type=int))
        return {"events": found, "cursor": cursor}

    return app
