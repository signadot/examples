"""Redis Streams helpers a platform team ships so app code works in Signadot sandboxes.

- Redis: a drop-in redis.Redis that adds the OpenTelemetry context to XADD.
- StreamConsumer: reads a stream through a consumer group and hands the app
  only the entries meant for this workload (baseline or sandbox).

StreamConsumer needs a client created with decode_responses=True. Routing is on
in sandboxes and in workloads that set SIGNADOT_BASELINE_NAME (and
SIGNADOT_BASELINE_NAMESPACE); elsewhere, such as a cluster without Signadot,
it processes every entry.
"""

from .client import Redis
from .consumer import StreamConsumer

__all__ = ["Redis", "StreamConsumer"]
