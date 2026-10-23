"""Signadot Routes API client.

Answers one question for a stream consumer: should this workload process an
entry carrying a given routing key? The answer comes from the routing rules the
Signadot Operator publishes for this workload's baseline (the Deployment that
sandboxes fork).
"""

import logging
import os
import threading
import time

import requests

ROUTING_KEY = "sd-routing-key"

log = logging.getLogger("platform_redis")


class RoutingRules:
    def __init__(self, routeserver, baseline_kind, baseline_namespace, baseline_name,
                 sandbox_name="", sandbox_routing_key="", interval=5.0):
        self._url = f"http://{routeserver}/api/v1/workloads/routing-rules"
        self._params = {
            "baselineKind": baseline_kind,
            "baselineNamespace": baseline_namespace,
            "baselineName": baseline_name,
        }
        self.sandbox_name = sandbox_name
        self.sandbox_routing_key = sandbox_routing_key
        self.interval = interval
        # Routing keys that send traffic to any sandbox of this baseline.
        self._sandbox_keys = frozenset()
        # Routing keys that send traffic to this sandbox (its own key and the
        # keys of route groups it belongs to).
        self._own_keys = frozenset()
        self._ready = threading.Event()

    @classmethod
    def from_env(cls):
        # SIGNADOT_SANDBOX_NAME and SIGNADOT_SANDBOX_ROUTING_KEY are set by the
        # Signadot Operator in sandboxed pods; the baseline identity is set in
        # the Deployment. Without either, routing is off (e.g. in a cluster
        # without Signadot) and None is returned.
        if not os.getenv("SIGNADOT_BASELINE_NAME") and not os.getenv("SIGNADOT_SANDBOX_NAME"):
            return None
        return cls(
            routeserver=os.getenv("SIGNADOT_ROUTESERVER", "routeserver.signadot.svc:7778"),
            baseline_kind=os.getenv("SIGNADOT_BASELINE_KIND", "Deployment"),
            baseline_namespace=os.environ["SIGNADOT_BASELINE_NAMESPACE"],
            baseline_name=os.environ["SIGNADOT_BASELINE_NAME"],
            sandbox_name=os.getenv("SIGNADOT_SANDBOX_NAME", ""),
            sandbox_routing_key=os.getenv("SIGNADOT_SANDBOX_ROUTING_KEY", ""),
        )

    @property
    def in_sandbox(self):
        return self.sandbox_name != ""

    def refresh(self):
        resp = requests.get(self._url, params=self._params, timeout=5)
        resp.raise_for_status()
        rules = resp.json().get("routingRules") or []
        sandbox_keys = frozenset(r["routingKey"] for r in rules)
        own_keys = frozenset(r["routingKey"] for r in rules
                             if r["destinationSandbox"]["name"] == self.sandbox_name)
        if sandbox_keys != self._sandbox_keys or not self._ready.is_set():
            log.info("routing keys for sandboxes of %s: %s",
                     self._params["baselineName"], sorted(sandbox_keys))
        self._sandbox_keys, self._own_keys = sandbox_keys, own_keys
        self._ready.set()

    def start(self):
        threading.Thread(target=self._poll, name="routing-rules", daemon=True).start()

    def _poll(self):
        while True:
            try:
                self.refresh()
            except Exception as e:  # keep the last known rules
                log.warning("could not refresh routing rules: %s", e)
            time.sleep(self.interval)

    def wait_ready(self, timeout=None):
        return self._ready.wait(timeout)

    def should_process(self, routing_key):
        if self.in_sandbox:
            # Process only what is routed to this sandbox.
            return routing_key is not None and (
                routing_key == self.sandbox_routing_key or routing_key in self._own_keys)
        # Baseline: process everything except what a sandbox has claimed.
        return routing_key not in self._sandbox_keys
