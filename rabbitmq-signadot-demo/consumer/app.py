import json
import logging
import os
import re
import signal
import threading
import time
from typing import Optional, Set

import pika
import requests
from opentelemetry.baggage import get_baggage  # read-only; OTel extracts it from AMQP

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(levelname)s - %(message)s",
)

def _parse_rabbitmq_port() -> int:
    raw = os.environ.get("RABBITMQ_PORT", "5672")
    if raw.startswith("tcp://"):
        m = re.search(r":(\d+)$", raw)
        if m:
            return int(m.group(1))
        logging.warning("Could not parse RABBITMQ_PORT '%s'; falling back to 5672", raw)
        return 5672
    try:
        return int(raw)
    except ValueError:
        logging.warning("Could not parse RABBITMQ_PORT '%s'; falling back to 5672", raw)
        return 5672

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = _parse_rabbitmq_port()
CUSTOMER_EXCHANGE = os.environ.get("CUSTOMER_EXCHANGE", "orders_exchange")

ROUTESERVER_URL = os.environ.get("ROUTESERVER_URL", "http://routeserver.signadot.svc:7778")
BASELINE_KIND = os.environ.get("BASELINE_KIND", "Deployment")

def _detect_namespace() -> str:
    if ns := os.environ.get("BASELINE_NAMESPACE"):
        return ns
    if ns := os.environ.get("POD_NAMESPACE"):
        return ns
    try:
        with open("/var/run/secrets/kubernetes.io/serviceaccount/namespace", "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return "rabbitmq-demo"

BASELINE_NAMESPACE = _detect_namespace()
BASELINE_NAME = os.environ.get("BASELINE_NAME", "consumer")

class SignadotConsumer:
    def __init__(self) -> None:
        self.sandbox_routing_key: Optional[str] = os.environ.get("SIGNADOT_SANDBOX_ROUTING_KEY")
        self._sandbox_name_env: str = os.environ.get("SIGNADOT_SANDBOX_NAME", "")
        self.sandbox_name: str = self._sandbox_name_env or "Baseline"
        self.is_baseline: bool = not bool(self.sandbox_routing_key)

        # Baseline: keys of every sandbox or route group that forks this consumer.
        # Sandbox: keys that route to this sandbox (its own key plus any route group it is in).
        self._active_routes: Set[str] = set()
        self._routes_lock = threading.Lock()
        self._stop_event = threading.Event()

        params = pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT)
        self.connection = pika.BlockingConnection(params)
        self.channel = self.connection.channel()
        self.channel.exchange_declare(exchange=CUSTOMER_EXCHANGE, exchange_type="topic", durable=True)

        logging.info("[%s] Initialized (is_baseline=%s)", self.sandbox_name, self.is_baseline)

    def _start_route_updater(self) -> None:
        def update_routes() -> None:
            while not self._stop_event.is_set():
                try:
                    url = (
                        f"{ROUTESERVER_URL}/api/v1/workloads/routing-rules"
                        f"?baselineKind={BASELINE_KIND}"
                        f"&baselineNamespace={BASELINE_NAMESPACE}"
                        f"&baselineName={BASELINE_NAME}"
                    )
                    if not self.is_baseline:
                        url += f"&destinationSandboxName={self._sandbox_name_env}"
                    resp = requests.get(url, timeout=5)
                    resp.raise_for_status()
                    data = resp.json()
                    rules = data.get("routingRules", [])
                    active = {r.get("routingKey") for r in rules if r.get("routingKey")}
                    with self._routes_lock:
                        self._active_routes = active
                    logging.info("[%s] Active sandbox keys: %s", self.sandbox_name, self._active_routes)
                except Exception as e:
                    logging.warning("[%s] Route update error: %s", self.sandbox_name, e)
                time.sleep(10)

        threading.Thread(target=update_routes, daemon=True).start()

    def _effective_routing_key(self) -> Optional[str]:
        # Source of truth: OTel baggage extracted by pika instrumentation.
        return get_baggage("sd-routing-key")

    def _should_process(self, properties: pika.BasicProperties) -> bool:
        msg_key = self._effective_routing_key()

        if not self.is_baseline:
            with self._routes_lock:
                my_keys = self._active_routes | {self.sandbox_routing_key}
            should = msg_key in my_keys
            logging.info("[%s] Message routing_key=%s, my_keys=%s -> process=%s",
                         self.sandbox_name, msg_key, sorted(my_keys), should)
            return should

        if not msg_key:
            logging.info("[%s] ACCEPT (no routing key)", self.sandbox_name)
            return True

        with self._routes_lock:
            is_active = msg_key in self._active_routes

        if not is_active:
            logging.info("[%s] ACCEPT (inactive/other-service key '%s')", self.sandbox_name, msg_key)
            return True

        logging.info("[%s] SKIP (active sandbox key '%s')", self.sandbox_name, msg_key)
        return False

    def _on_message(self, ch, method, properties, body) -> None:
        try:
            if self._should_process(properties):
                try:
                    self.handle_message(body, getattr(properties, "headers", {}) or {})
                except Exception as e:
                    logging.error("[%s] Error in handle_message: %s", self.sandbox_name, e)
        finally:
            ch.basic_ack(delivery_tag=method.delivery_tag)

    def start(self) -> None:
        queue_name = os.environ.get("QUEUE_NAME", f"consumer-{self.sandbox_name}")
        durable = (os.environ.get("QUEUE_DURABLE", "true" if self.is_baseline else "false").lower() == "true")
        exclusive = (os.environ.get("QUEUE_EXCLUSIVE", "false").lower() == "true")
        auto_delete = (os.environ.get("QUEUE_AUTO_DELETE", "false" if self.is_baseline else "true").lower() == "true")

        res = self.channel.queue_declare(queue=queue_name, durable=durable, exclusive=exclusive, auto_delete=auto_delete)
        self.queue_name = res.method.queue
        logging.info("[%s] Declared queue '%s' (durable=%s, exclusive=%s, auto_delete=%s)",
                     self.sandbox_name, self.queue_name, durable, exclusive, auto_delete)

        self.channel.queue_bind(exchange=CUSTOMER_EXCHANGE, queue=self.queue_name, routing_key="#")
        self._start_route_updater()

        self.channel.basic_consume(queue=self.queue_name, on_message_callback=self._on_message)
        logging.info("[%s] Waiting for messages. Press CTRL+C to exit.", self.sandbox_name)

        def _graceful_stop(signum, frame):
            logging.info("[%s] Received signal %s; stopping...", self.sandbox_name, signum)
            self.stop()

        signal.signal(signal.SIGTERM, _graceful_stop)
        signal.signal(signal.SIGINT, _graceful_stop)

        try:
            self.channel.start_consuming()
        except Exception as e:
            logging.error("[%s] Consuming stopped due to error: %s", self.sandbox_name, e)
            self.stop()

    def stop(self) -> None:
        self._stop_event.set()
        try:
            if self.channel.is_open:
                self.channel.stop_consuming()
        finally:
            if self.connection.is_open:
                self.connection.close()
        logging.info("[%s] Consumer stopped", self.sandbox_name)

    def handle_message(self, body: bytes, headers: dict) -> None:
        raise NotImplementedError("Implement in subclass.")

class OrderProcessorConsumer(SignadotConsumer):
    def handle_message(self, body: bytes, headers: dict) -> None:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            logging.error("[%s] Invalid JSON payload: %r", self.sandbox_name, body)
            return
        order_id = payload.get("order_id", "unknown")
        amount = payload.get("amount", 0)
        logging.info("[%s] --> PROCESSING ORDER %s amount=%s", self.sandbox_name, order_id, amount)
        time.sleep(1.0)
        logging.info("[%s] --> COMPLETED ORDER %s", self.sandbox_name, order_id)

if __name__ == "__main__":
    OrderProcessorConsumer().start()
