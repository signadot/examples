"""
Tiny helpers for talking to the local Dapr sidecar over its HTTP API.

Plain HTTP instead of a Dapr SDK, so every hop is visible in the code.
API reference: https://docs.dapr.io/reference/api/
"""
import os
from typing import Mapping, Optional

import httpx

DAPR_URL = f"http://localhost:{os.environ.get('DAPR_HTTP_PORT', '3500')}"

_app_id: Optional[str] = None


async def app_id() -> str:
    """This app's Dapr app-id, read once from the sidecar's metadata API.

    A sandbox fork runs under a different app-id (see ../../signadot/*.yaml),
    so reporting it shows which instance handled a request.
    """
    global _app_id
    if _app_id is None:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{DAPR_URL}/v1.0/metadata")
            resp.raise_for_status()
            _app_id = resp.json()["id"]
    return _app_id


async def invoke(target: str, path: str, *, headers: Mapping[str, str], verb: str = "GET", json=None) -> httpx.Response:
    """Service invocation. `target` is an app-id or an HTTPEndpoint name.

    The sidecar forwards `headers` to the callee, which is how the Signadot
    routing context (`baggage`) reaches it.
    """
    async with httpx.AsyncClient(timeout=10) as client:
        return await client.request(verb, f"{DAPR_URL}/v1.0/invoke/{target}/method/{path}", headers=dict(headers), json=json)


async def publish(pubsub: str, topic: str, cloudevent: dict) -> None:
    """Publish a CloudEvent we built ourselves, so it can carry extension attributes."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{DAPR_URL}/v1.0/publish/{pubsub}/{topic}",
            headers={"content-type": "application/cloudevents+json"},
            json=cloudevent,
        )
        resp.raise_for_status()
