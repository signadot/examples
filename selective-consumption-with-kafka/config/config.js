
module.exports = {
    // Ports
    frontendPort: process.env.FRONTEND_PORT || 4000,
    producerPort: process.env.PRODUCER_PORT || 4001,

    // Addresses
    producerHost: process.env.PRODUCER_HOST || "producer.kafka-demo.svc",
    redisURL: process.env.REDIS_URL || "redis://redis.kafka-demo.svc:6379",
    kafkaAddr: process.env.KAFKA_ADDR || "kafka-headless.kafka-demo.svc:9092",
    routeServerAddr: "routeserver.signadot.svc:7778",

    // Baseline
    baselineKind: process.env.BASELINE_KIND || "Deployment",
    baselineNamespace: process.env.BASELINE_NAMESPACE || "kafka-demo",
    baselineName: process.env.BASELINE_NAME || "",

    // Sandbox
    sandboxName: process.env.SIGNADOT_SANDBOX_NAME || "",

    // Kafka
    kafkaTopic: process.env.KAFKA_TOPIC || "kafka-demo",
}