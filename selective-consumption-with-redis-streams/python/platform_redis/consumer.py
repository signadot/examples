"""Consume a Redis stream so that baseline and sandboxed consumers share it.

Every consumer group receives every entry, so the baseline and each sandbox
read through their own group, and each one decides per entry whether the entry
is meant for it. The app only supplies a handler.
"""

import logging
import time

import redis
from opentelemetry import baggage, context, propagate, trace

from .routes import ROUTING_KEY, RoutingRules

log = logging.getLogger("platform_redis")
tracer = trace.get_tracer("platform_redis")


class StreamConsumer:
    def __init__(self, client, stream, group, name, block_ms=5000, claim_idle_ms=60_000,
                 on_ready=None):
        if not client.get_connection_kwargs().get("decode_responses"):
            raise ValueError("StreamConsumer needs a client created with decode_responses=True")
        self.client = client
        self.stream = stream
        self.name = name
        self.block_ms = block_ms
        self.claim_idle_ms = claim_idle_ms
        self.on_ready = on_ready
        # None when Signadot routing isn't configured: then every entry is processed.
        self.rules = RoutingRules.from_env()
        self.in_sandbox = self.rules is not None and self.rules.in_sandbox
        # Never join the baseline's group from a sandbox: within a group each
        # entry goes to only one consumer, regardless of routing key.
        if self.in_sandbox:
            self.group = f"{group}-{self.rules.sandbox_routing_key}"
        else:
            self.group = group

    def run(self, handler):
        if self.rules is None:
            log.info("Signadot routing not configured; processing every entry")
        else:
            self.rules.start()
            log.info("waiting for routing rules")
            self.rules.wait_ready()
        self._create_group()
        if self.on_ready:
            self.on_ready()
        # Entries this consumer read before a restart but never acknowledged.
        self._read(handler, "0")
        last_reclaim = 0.0
        while True:
            if time.monotonic() - last_reclaim >= self.claim_idle_ms / 1000:
                self._reclaim(handler)
                last_reclaim = time.monotonic()
            self._read(handler, ">", block=self.block_ms)

    def _create_group(self):
        # A sandbox starts at "$" (new entries only) instead of replaying the
        # stream; the baseline starts at "0" so nothing published before its
        # first start is missed.
        start = "$" if self.in_sandbox else "0"
        while True:
            try:
                self.client.xgroup_create(self.stream, self.group, id=start, mkstream=True)
                log.info("created consumer group %s at %s", self.group, start)
                return
            except redis.ResponseError as e:
                if "BUSYGROUP" not in str(e):
                    raise
                log.info("using existing consumer group %s", self.group)
                return
            except redis.ConnectionError as e:
                log.warning("waiting for Redis: %s", e)
                time.sleep(2)

    def _read(self, handler, start_id, block=None):
        # ">" reads new entries; "0" re-reads this consumer's own pending ones
        # until there are none left.
        while True:
            response = self.client.xreadgroup(self.group, self.name, {self.stream: start_id},
                                              count=10, block=block)
            entries = [e for _, stream_entries in response or [] for e in stream_entries]
            for entry_id, fields in entries:
                self._handle(entry_id, fields, handler)
            if start_id == ">" or not entries:
                return

    def _reclaim(self, handler):
        # Take over entries that another consumer (e.g. a pod that was
        # replaced) read but never acknowledged.
        start = "0-0"
        while True:
            next_start, entries = self.client.xautoclaim(
                self.stream, self.group, self.name, min_idle_time=self.claim_idle_ms,
                start_id=start, count=10)[:2]
            for entry_id, fields in entries:
                self._handle(entry_id, fields, handler)
            if next_start == "0-0":
                return
            start = next_start

    def _should_process(self, routing_key):
        return self.rules is None or self.rules.should_process(routing_key)

    def _handle(self, entry_id, fields, handler):
        try:
            if fields is None:  # trimmed from the stream while pending
                return
            ctx = propagate.extract(fields)
            routing_key = baggage.get_baggage(ROUTING_KEY, ctx)
            app_fields = {k: v for k, v in fields.items()
                          if k not in propagate.get_global_textmap().fields}
            if not self._should_process(routing_key):
                log.info("skipped %s (routing key %s)", entry_id, routing_key)
                return
            log.info("processing %s (routing key %s)", entry_id, routing_key)
            # Make the entry's context current, so the handler's outbound
            # calls carry the routing key.
            token = context.attach(ctx)
            try:
                with tracer.start_as_current_span(f"{self.stream} process",
                                                  kind=trace.SpanKind.CONSUMER):
                    handler(entry_id, app_fields)
            except Exception:
                log.exception("handler failed for %s", entry_id)
            finally:
                context.detach(token)
        finally:
            # Acknowledge processed and skipped entries alike, or they stay in
            # this group's pending entries list forever.
            self.client.xack(self.stream, self.group, entry_id)
