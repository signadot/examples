# Selective Consumption with Redis Streams

These examples show how services that publish to and consume from
[Redis Streams](https://redis.io/docs/latest/develop/data-types/streams/) work with Signadot
sandboxes. The routing key travels inside each stream entry, every sandboxed consumer reads
through its own consumer group, and each consumer, baseline or sandboxed, processes only the
entries meant for it. The Signadot-specific code lives in a thin wrapper over the Redis client,
so application code stays plain.

> **Step-by-step tutorial:** [Test Redis Streams Consumers with Sandboxes](https://www.signadot.com/docs/tutorials/testing-redis-streams?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=redis-streams)
> explains how this example works and walks through every step.

| Language | Tutorial |
|---|---|
| Python | [python/](python/) |

## Next steps

- [Test Redis Streams Consumers with Sandboxes](https://www.signadot.com/docs/tutorials/testing-redis-streams?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=redis-streams): the full tutorial for this example.
- [Messaging and workflow tutorials](https://www.signadot.com/docs/tutorials/messaging-and-workflows?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=redis-streams): Kafka, RabbitMQ, Amazon SQS, Google Pub/Sub, Redis Streams, Temporal and Dapr.
- New to Signadot? [Create a free account](https://www.signadot.com/signup/?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=redis-streams) (no credit card), then try it on your own services.
- Questions? Ask in the [Signadot community Slack](https://join.slack.com/t/signadotcommunity/shared_invite/zt-1estxm8pv-qfiaNfiFFCaW~eUlXsVoEQ).
