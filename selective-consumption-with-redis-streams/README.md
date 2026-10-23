# Selective Consumption with Redis Streams

These examples show how services that publish to and consume from
[Redis Streams](https://redis.io/docs/latest/develop/data-types/streams/) work with Signadot
sandboxes. The routing key travels inside each stream entry, every sandboxed consumer reads
through its own consumer group, and each consumer, baseline or sandboxed, processes only the
entries meant for it. The Signadot-specific code lives in a thin wrapper over the Redis client,
so application code stays plain.

| Language | Tutorial |
|---|---|
| Python | [python/](python/) |
