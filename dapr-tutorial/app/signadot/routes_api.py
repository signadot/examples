"""
Selective consumption: ask Signadot's Routes API whether *this* workload should
process a message carrying a given routing key.

Every consumer (baseline and sandboxed) receives every message, because each
Dapr app-id is its own consumer group. The Routes API tells us which routing
keys currently point at which sandbox of our baseline workload, so exactly one
consumer acts on each message:

  * sandbox consumer:  process only keys that route to this sandbox
  * baseline consumer: process everything except keys claimed by a sandbox

Same pattern as ../../selective-consumption-with-kafka and ../../temporal-tutorial.
Docs: https://github.com/signadot/routesapi
"""
import asyncio
import logging
import os
from typing import Optional, Set

import httpx

log = logging.getLogger("signadot.routes")

ROUTESERVER = os.environ.get("ROUTESERVER_ADDR", "http://routeserver.signadot.svc:7778")


class RoutesClient:
    def __init__(
        self,
        baseline_name: str,
        baseline_namespace: str,
        baseline_kind: str = "Deployment",
        sandbox_name: str = "",
        refresh_seconds: int = 5,
    ):
        self.sandbox_name = sandbox_name
        self.refresh_seconds = refresh_seconds
        self.params = {
            "baselineKind": baseline_kind,
            "baselineNamespace": baseline_namespace,
            "baselineName": baseline_name,
        }
        if sandbox_name:
            # Only the rules whose destination is this sandbox.
            self.params["destinationSandboxName"] = sandbox_name
        self.routing_keys: Set[str] = set()

    @classmethod
    def from_env(cls) -> "RoutesClient":
        """Baseline identity comes from the Deployment manifest.
        SIGNADOT_SANDBOX_NAME is injected by the Signadot operator into forked
        workloads only, so it is empty on the baseline."""
        return cls(
            baseline_name=os.environ["BASELINE_NAME"],
            baseline_namespace=os.environ["BASELINE_NAMESPACE"],
            sandbox_name=os.environ.get("SIGNADOT_SANDBOX_NAME", ""),
        )

    @property
    def identity(self) -> str:
        return f"sandbox={self.sandbox_name}" if self.sandbox_name else "baseline"

    async def run(self) -> None:
        """Poll the Routes API forever. Start this as a background task."""
        async with httpx.AsyncClient(timeout=5) as client:
            while True:
                await self._refresh(client)
                await asyncio.sleep(self.refresh_seconds)

    async def _refresh(self, client: httpx.AsyncClient) -> None:
        try:
            resp = await client.get(f"{ROUTESERVER}/api/v1/workloads/routing-rules", params=self.params)
            resp.raise_for_status()
            rules = resp.json().get("routingRules") or []
            keys = {rule["routingKey"] for rule in rules}
        except Exception as exc:  # keep the last good snapshot on transient errors
            log.warning("routes api: %s", exc)
            return
        if keys != self.routing_keys:
            log.info("routes api (%s): routing keys now %s", self.identity, sorted(keys))
            self.routing_keys = keys

    def should_process(self, routing_key: Optional[str]) -> bool:
        if self.sandbox_name:
            return routing_key is not None and routing_key in self.routing_keys
        return routing_key is None or routing_key not in self.routing_keys
