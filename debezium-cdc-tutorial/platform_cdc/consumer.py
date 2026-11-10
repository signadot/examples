"""Consume a Debezium topic so that baseline and sandboxed consumers share it.

Every Kafka consumer group receives every change event, so the baseline and
each sandbox read through their own group, and each one decides per event
whether the event is meant for it. The app only supplies a handler.
"""

import json
import logging
from dataclasses import dataclass

from confluent_kafka import Consumer
from opentelemetry import baggage, context, propagate, trace

from .routes import ROUTING_KEY, RoutingRules

log = logging.getLogger("platform_cdc")
tracer = trace.get_tracer("platform_cdc")


@dataclass
class Change:
    """One row change, as flattened by Debezium's ExtractNewRecordState."""
    topic: str
    op: str    # c = insert, u = update, d = delete, r = read by the initial snapshot
    row: dict  # the row after the change (before it, for a delete)


class ChangeConsumer:
    def __init__(self, bootstrap_servers, topic, group, on_ready=None, config=None):
        self.topic = topic
        self.on_ready = on_ready
        # None when Signadot routing isn't configured: then every event is processed.
        self.rules = RoutingRules.from_env()
        self.in_sandbox = self.rules is not None and self.rules.in_sandbox
        # Never join the baseline's group from a sandbox: within a group each
        # event goes to only one consumer, regardless of routing key.
        if self.in_sandbox:
            self.group = f"{group}-{self.rules.sandbox_routing_key}"
        else:
            self.group = group
        self._consumer = Consumer({
            "bootstrap.servers": bootstrap_servers,
            "group.id": self.group,
            # A new sandbox group starts at the end of the topic instead of
            # replaying it; the baseline starts at the beginning so nothing
            # captured before its first start is missed.
            "auto.offset.reset": "latest" if self.in_sandbox else "earliest",
            # Commit an event's offset only after it was handled or skipped.
            "enable.auto.offset.store": False,
            **(config or {}),
        })

    def run(self, handler):
        if self.rules is None:
            log.info("Signadot routing not configured; processing every change event")
        else:
            self.rules.start()
            log.info("waiting for routing rules")
            self.rules.wait_ready()
        log.info("subscribing to %s with consumer group %s", self.topic, self.group)
        self._consumer.subscribe([self.topic], on_assign=self._on_assign)
        # The baseline is ready now: its group keeps its place in the topic. A
        # sandbox is ready once it has partitions, because its new group
        # starts at the end of the topic and would miss earlier events.
        if not self.in_sandbox:
            self._ready()
        try:
            while True:
                msg = self._consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    log.warning("consumer error: %s", msg.error())
                    continue
                self._handle(msg, handler)
                self._consumer.store_offsets(msg)
        finally:
            self._consumer.close()

    def _on_assign(self, consumer, partitions):
        log.info("assigned %s", [f"{p.topic}[{p.partition}]" for p in partitions])
        if partitions:
            self._ready()

    def _ready(self):
        if self.on_ready:
            self.on_ready()

    def _should_process(self, routing_key):
        return self.rules is None or self.rules.should_process(routing_key)

    def _handle(self, msg, handler):
        where = f"{msg.topic()}[{msg.partition()}]@{msg.offset()}"
        # Debezium put the context that was stored with the row into the
        # event's headers, where any Kafka consumer expects it.
        carrier = {k: v.decode() for k, v in msg.headers() or [] if v is not None}
        ctx = propagate.extract(carrier)
        routing_key = baggage.get_baggage(ROUTING_KEY, ctx)
        if not self._should_process(routing_key):
            log.info("skipped %s (routing key %s)", where, routing_key)
            return
        if msg.value() is None:  # tombstone
            return
        row = json.loads(msg.value())
        op = row.pop("__op", "")
        row.pop("__deleted", None)
        log.info("processing %s (routing key %s)", where, routing_key)
        # Make the event's context current, so the handler's outbound calls
        # and database writes carry the routing key.
        token = context.attach(ctx)
        try:
            with tracer.start_as_current_span(f"{msg.topic()} process",
                                              kind=trace.SpanKind.CONSUMER):
                handler(Change(topic=msg.topic(), op=op, row=row))
        except Exception:
            log.exception("handler failed for %s", where)
        finally:
            context.detach(token)
