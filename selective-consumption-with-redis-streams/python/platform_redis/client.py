"""A drop-in redis.Redis whose XADD carries the OpenTelemetry context."""

import redis
from opentelemetry import propagate


class Redis(redis.Redis):
    def xadd(self, name, fields, *args, **kwargs):
        # Stream entries have no headers, so the W3C trace context and baggage
        # (which holds the Signadot routing key) travel as extra fields.
        carrier = {}
        propagate.inject(carrier)
        return super().xadd(name, {**fields, **carrier}, *args, **kwargs)
