"""Selective consumption with shared Redis records and atomic deduplication."""
import asyncio
from collections import Counter
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
import json
import logging

from fastapi import FastAPI, Query, Request
from pydantic import ValidationError
from redis.exceptions import RedisError

from common.config import Settings
from common.dapr import DaprClient
from common.models import OrderInput
from common.service import add_diagnostics, close_clients, install_errors, request_context
from common.store import LegacyStoreError, OrderStore
from signadot.dapr import validate_cloud_event
from signadot.routes_api import RouteCache, RoutesClient
from signadot.routing import RoutingError, routing_key
from signadot.subscription import SubscriptionGuard

log = logging.getLogger("order-processor")


class Consumer:
    def __init__(self, settings, cache, store):
        self.settings, self.cache, self.store = settings, cache, store
        self.guard = SubscriptionGuard(settings.workload, app_id=settings.app_id, sandbox=settings.sandbox,
                                       app_ids=settings.app_ids, rules=cache.rules)
        self.counts = Counter()  # Diagnostic only; records and attempts live in Redis.

    def reply(self, action, status, event, key=None, **details):
        self.counts[action] += 1
        result = {"action": action, "status": status, "id": event.get("id"),
                  "source": event.get("source"), "routing_key": key,
                  **self.settings.identity, **details}
        log.info(json.dumps(result))
        return {"status": status, "action": action, **details}

    async def receive(self, event, headers):
        if not isinstance(event, dict):
            return {"status": "DROP", "action": "drop", "reason": "CloudEvent must be an object"}
        key = None
        try:
            key = validate_cloud_event(event, headers)
        except (ValueError, RoutingError) as exc:
            return self.reply("drop", "DROP", event, key, reason=str(exc))
        try:
            owns = self.guard.owns(key)
        except RoutingError as exc:
            return self.reply("retry", "RETRY", event, key, reason=str(exc))
        if not owns:
            return self.reply("skip", "SUCCESS", event, key, reason="different workload owner")
        # Only the selected owner interprets the business schema. A fork may
        # accept a different event type or payload without other groups rejecting it.
        try:
            source, event_id = event["source"], event["id"]
            if event["type"] != "order.created":
                raise ValueError("expected an order.created event")
            data = event.get("data")
            if not isinstance(data, dict):
                raise ValueError("CloudEvent data must be an order object")
            validated = OrderInput.model_validate({name: data[name] for name in
                ("item", "quantity", "simulate_failures") if name in data})
            if data.get("id") != event_id or data.get("created_by") != source:
                raise ValueError("order identity must agree with CloudEvent source/id")
            if data.get("routing_key") != key:
                raise ValueError("order routing_key must agree with CloudEvent context")
            if type(data.get("total_cents")) is not int or data["total_cents"] < 0:
                raise ValueError("order requires nonnegative integer total_cents")
        except (ValueError, ValidationError) as exc:
            return self.reply("drop", "DROP", event, key, reason=str(exc))
        record = {**data, "source": source, "id": event_id, "routing_key": key,
                  "processed_by": self.settings.app_id, "fulfillment": self.settings.fulfillment,
                  "processor_sandbox": self.settings.sandbox or "baseline", "pod": self.settings.pod,
                  "processed_at": datetime.now(timezone.utc).isoformat()}
        try:
            action, result = await self.store.commit(record, validated.simulate_failures)
        except (RedisError, OSError, TimeoutError) as exc:
            return self.reply("retry", "RETRY", event, key, reason=f"Redis unavailable: {exc}")
        if action == "retry":
            return self.reply("retry", "RETRY", event, key, reason="simulated transient failure",
                              delivery_attempt=result)
        return self.reply(action, "SUCCESS", event, key, delivery_attempt=result["delivery_attempt"])


def create_app(settings=None, *, routes=None, dapr=None, cache=None, store=None):
    settings = settings or Settings.from_env("order-processor")
    routes, dapr = routes or RoutesClient(settings.routes_url), dapr or DaprClient(settings.dapr_url)
    cache = cache or RouteCache(settings.workload, routes, settings.routes_refresh, settings.routes_max_age)
    store = store or OrderStore(settings.redis_url, settings.namespace, settings.app_id)
    consumer = Consumer(settings, cache, store)

    @asynccontextmanager
    async def lifespan(_):
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
        logging.getLogger("httpx").setLevel(logging.WARNING)
        task = asyncio.create_task(cache.run())
        try:
            yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            await close_clients(store, routes, dapr)

    app = FastAPI(title="Order processor", lifespan=lifespan)
    app.state.consumer = consumer
    install_errors(app)
    add_diagnostics(app, settings, routes, dapr, cache=cache, store=store)

    @app.exception_handler(RedisError)
    async def redis_failure(_, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content={"error": "redis-unavailable", "detail": str(exc)})

    @app.exception_handler(LegacyStoreError)
    async def legacy_ledger(_, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content={"error": "ledger-upgrade-required", "detail": str(exc)})

    @app.get("/dapr/subscribe")
    async def subscribe():
        # Component consumerID defaults to the app ID. Never use a Pod identifier:
        # replicas compete within one group; independent worker forks each get a copy.
        return [{"pubsubname": settings.pubsub, "topic": settings.topic, "route": "/orders",
                 "deadLetterTopic": settings.dead_letter_topic}]

    @app.post("/orders")
    async def on_order(request: Request):
        try:
            event = await request.json()
        except (ValueError, UnicodeDecodeError):
            return {"status": "DROP", "action": "drop", "reason": "invalid CloudEvent JSON"}
        # Dapr interprets RETRY only with the explicit component inbound retry
        # policy generated by the bootstrap before forwarding to the dead-letter topic.
        return await consumer.receive(event, request.headers)

    @app.get("/processed")
    async def list_processed(request: Request, all_contexts: bool = Query(False, alias="all")):
        key = routing_key(request_context(request))
        # all=true explicitly exports complete diagnostic history for verification.
        records = (await store.state())["records"] if all_contexts else await store.records(key, limit=100)
        return {"routing_key": key, "orders": records, "limit": None if all_contexts else 100,
                **settings.identity}

    return app


app = create_app()
