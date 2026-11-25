"""Runtime settings, including the baseline app IDs this Pod invokes.

Only baselines are configured. A fork's app ID comes from the naming rule in
signadot.appid, so creating or deleting a sandbox changes nothing here.
"""
from dataclasses import dataclass
import os

from signadot.routes_api import AppIDs, Workload


@dataclass(frozen=True)
class Settings:
    app_id: str
    baseline_name: str
    namespace: str
    sandbox: str = ""
    pod: str = "local"
    routes_url: str = "http://routeserver.signadot.svc:7778"
    dapr_url: str = "http://127.0.0.1:3500"
    redis_url: str = "redis://redis:6379/0"
    pubsub: str = "pubsub"
    topic: str = "orders"
    discount_percent: int = 0
    fulfillment: str = "standard"
    frontend_name: str = "frontend"
    checkout_name: str = "checkout"
    processor_name: str = "order-processor"
    frontend_app_id: str = "frontend"
    checkout_app_id: str = "checkout"
    processor_app_id: str = "order-processor"
    console_variant: str = "baseline"
    routes_refresh: float = 2.0
    routes_max_age: float = 15.0

    @classmethod
    def from_env(cls, baseline_name):
        return cls(
            app_id=os.environ.get("DAPR_APP_ID", baseline_name),
            baseline_name=os.environ.get("BASELINE_NAME", baseline_name),
            namespace=os.environ.get("BASELINE_NAMESPACE", "dapr-tutorial"),
            sandbox=os.environ.get("SIGNADOT_SANDBOX_NAME", ""),
            pod=os.environ.get("HOSTNAME", "local"),
            routes_url=os.environ.get("ROUTESERVER_ADDR", cls.routes_url),
            dapr_url=os.environ.get("DAPR_URL", "http://127.0.0.1:" + os.environ.get("DAPR_HTTP_PORT", "3500")),
            redis_url=os.environ.get("REDIS_URL", cls.redis_url),
            pubsub=os.environ.get("PUBSUB_NAME", "pubsub"),
            topic=os.environ.get("ORDERS_TOPIC", "orders"),
            discount_percent=int(os.environ.get("DISCOUNT_PERCENT", os.environ.get("CHECKOUT_DISCOUNT_PERCENT", "0"))),
            fulfillment=os.environ.get("FULFILLMENT_MODE", "standard"),
            frontend_name=os.environ.get("FRONTEND_BASELINE_NAME", "frontend"),
            checkout_name=os.environ.get("CHECKOUT_BASELINE_NAME", "checkout"),
            processor_name=os.environ.get("PROCESSOR_BASELINE_NAME", "order-processor"),
            frontend_app_id=os.environ.get("FRONTEND_APP_ID", "frontend"),
            checkout_app_id=os.environ.get("CHECKOUT_APP_ID", "checkout"),
            processor_app_id=os.environ.get("PROCESSOR_APP_ID", "order-processor"),
            console_variant=os.environ.get("CONSOLE_VARIANT", "baseline"),
            routes_refresh=float(os.environ.get("ROUTES_REFRESH_SECONDS", "2")),
            routes_max_age=float(os.environ.get("ROUTES_MAX_AGE_SECONDS", "15")),
        )

    @property
    def workload(self):
        return Workload("Deployment", self.namespace, self.baseline_name)

    @property
    def app_ids(self):
        """Baseline app IDs for every workload in the tutorial, keyed by workload.

        The console is included so the order desk can show which app ID served each
        hop. Nothing invokes the console, so routing never asks for it.
        """
        def workload(name):
            return Workload("Deployment", self.namespace, name)
        return AppIDs({workload(self.frontend_name): self.frontend_app_id,
                       workload(self.checkout_name): self.checkout_app_id,
                       workload(self.processor_name): self.processor_app_id})

    @property
    def identity(self):
        return {"app_id": self.app_id, "sandbox": self.sandbox or "baseline", "pod": self.pod,
                "variant": self.console_variant}

    @property
    def routed_workloads(self):
        """Baselines this Pod resolves through the Routes API before invoking.

        The console is deliberately absent: a browser reaches it over ordinary
        HTTP, so Signadot's own routing selects the console fork and no
        application resolves an app ID for it.
        """
        return (self.checkout_name, self.processor_name)

    @property
    def dead_letter_topic(self):
        return os.environ.get("DEAD_LETTER_TOPIC", "orders-dlq-" + self.app_id)

