import asyncio
import httpx
from typing import Set


class RouteServerClient:
    """Periodically pulls routing rules from the Signadot RouteServer."""

    def __init__(self, server_addr: str, baseline_kind: str, baseline_namespace: str,
                 baseline_name: str, sandbox_name: str = "") -> None:
        self.server_addr = server_addr
        self.baseline_kind = baseline_kind
        self.baseline_namespace = baseline_namespace
        self.baseline_name = baseline_name
        self.sandbox_name = sandbox_name
        self.routing_keys: Set[str] = set()

    async def _pull_routes(self) -> None:
        url = f"http://{self.server_addr}/api/v1/workloads/routing-rules"
        params = {
            "baselineKind": self.baseline_kind,
            "baselineNamespace": self.baseline_namespace,
            "baselineName": self.baseline_name,
        }
        if self.sandbox_name:
            params["destinationSandboxName"] = self.sandbox_name
        try:
            resp = await httpx.get(url, params=params)
            data = resp.json()
            self.routing_keys = {
                r["routingKey"] for r in data.get("routingRules", [])
            }
        except Exception as exc:
            print(f"error contacting routeserver: {exc}")

    async def run(self) -> None:
        await self._pull_routes()
        while True:
            await asyncio.sleep(5)
            await self._pull_routes()

    def should_process(self, routing_key: str) -> bool:
        if self.sandbox_name:
            return routing_key in self.routing_keys
        return routing_key not in self.routing_keys
