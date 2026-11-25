"""Reusable native invocation and structured CloudEvent publishing helpers.

The caller supplies workload identities, event identity, and business payloads.
Injected RoutesClient and DaprClient instances retain their existing lifecycle;
this wrapper neither creates nor closes clients and adds no background tasks.
"""
from collections.abc import Mapping
from typing import Any

from signadot.routes_api import AppIDs, Workload
from signadot.routing import ROUTING_HEADERS, routing_headers, routing_key_from_event


def validate_cloud_event(event: Mapping, headers: Mapping[str, str]) -> str | None:
    """Validate this integration's envelope/context, leaving data to the handler.

    Event IDs are limited to 128 characters; source/type to 256. Data is optional
    in CloudEvents and is deliberately not inspected at the routing boundary.
    """
    if not isinstance(event, dict) or event.get("specversion") != "1.0":
        raise ValueError("expected a CloudEvent object with specversion 1.0")
    for name, limit in (("id", 128), ("source", 256), ("type", 256)):
        value = event.get(name)
        if not isinstance(value, str) or not value or len(value) > limit:
            raise ValueError(f"CloudEvent {name} must be a nonempty string of at most {limit} characters")
    return routing_key_from_event(event, headers)


def cloud_event(*, event_id: str, source: str, event_type: str, data: Any,
                headers: Mapping[str, str]) -> dict:
    """Build one JSON CloudEvent without inventing an ID or mutating its data.

    Stable source/id values belong to the producer so retries retain identity.
    Only normalized routing/trace context is included as envelope extensions.
    """
    context = routing_headers(headers)
    event = {"specversion": "1.0", "id": event_id, "source": source,
             "type": event_type, "datacontenttype": "application/json",
             "data": data, **context}
    validate_cloud_event(event, {})
    return event


class SignadotDaprClient:
    """Compose routing and native Dapr calls without application-specific policy."""

    def __init__(self, routes, dapr, app_ids: AppIDs, *,
                 max_age=15.0, refresh_seconds=2.0):
        self.routes, self.dapr, self.app_ids = routes, dapr, app_ids
        self.max_age, self.refresh_seconds = max_age, refresh_seconds

    async def invoke(self, workload: Workload, path: str, *, headers: Mapping[str, str],
                     verb="GET", json=None):
        # Reject malformed context before using the network.
        context = routing_headers(headers)
        resolution = await self.routes.resolve(
            workload, context, self.app_ids, max_age=self.max_age,
            refresh_seconds=self.refresh_seconds)
        return await self.dapr.invoke(resolution, path, headers=context, verb=verb, json=json)

    async def publish(self, pubsub: str, topic: str, *, event_id: str, source: str,
                      event_type: str, data: Any, headers: Mapping[str, str]) -> dict:
        event = cloud_event(event_id=event_id, source=source, event_type=event_type,
                            data=data, headers=headers)
        context = {name: event[name] for name in ROUTING_HEADERS if name in event}
        await self.dapr.publish(pubsub, topic, event, context)
        return event
