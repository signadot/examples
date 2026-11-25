"""Checkout publishes a stable CloudEvent carrying its caller's routing context."""
from datetime import datetime, timezone
import uuid

from fastapi import FastAPI, Request

from common.config import Settings
from common.dapr import DaprClient
from common.models import OrderInput
from common.service import add_diagnostics, client_lifespan, install_errors, request_context
from signadot.dapr import SignadotDaprClient
from signadot.routes_api import RoutesClient
from signadot.routing import routing_key

UNIT_PRICE_CENTS = 1200


def create_app(settings=None, *, routes=None, dapr=None):
    settings = settings or Settings.from_env("checkout")
    if not 0 <= settings.discount_percent <= 100:
        raise ValueError("DISCOUNT_PERCENT must be between 0 and 100")
    routes, dapr = routes or RoutesClient(settings.routes_url), dapr or DaprClient(settings.dapr_url)
    integration = SignadotDaprClient(routes, dapr, settings.app_ids,
                                     max_age=settings.routes_max_age,
                                     refresh_seconds=settings.routes_refresh)
    app = FastAPI(title="Checkout", lifespan=client_lifespan(routes, dapr))
    install_errors(app)
    add_diagnostics(app, settings, routes, dapr)

    @app.post("/orders")
    async def create_order(order: OrderInput, request: Request):
        headers = request_context(request)
        key = routing_key(headers)
        order_id = order.id or uuid.uuid4().hex
        total = UNIT_PRICE_CENTS * order.quantity * (100 - settings.discount_percent) // 100
        record = {"id": order_id, "item": order.item, "quantity": order.quantity,
                  "unit_price_cents": UNIT_PRICE_CENTS, "total_cents": total,
                  "discount_percent": settings.discount_percent, "created_by": settings.app_id,
                  "routing_key": key, "simulate_failures": order.simulate_failures,
                  "created_at": datetime.now(timezone.utc).isoformat()}
        event = await integration.publish(settings.pubsub, settings.topic,
                                           event_id=order_id, source=settings.app_id,
                                           event_type="order.created", data=record, headers=headers)
        return {"order_id": order_id, **record, "handled_by": settings.identity,
                "published": True, "source": event["source"]}

    return app


app = create_app()
