
module.exports = {
    // Ports
    frontendPort: process.env.FRONTEND_PORT || 4000,
    producerPort: process.env.PRODUCER_PORT || 4001,

    // Addresses
    producerAddr: process.env.PRODUCER_ADDR || "localhost:4001",
    redisURL: process.env.REDIS_URL || "redis://redis.kafka-demo.svc:6379",

    // Baseline
    baselineKind: process.env.BASELINE_KIND || "Deployment",
    baselineNamespace: process.env.BASELINE_NAMESPACE || "kafka-demo",
    baselineName: process.env.BASELINE_NAME || "",

    // Sandbox
    sandboxName: process.env.SIGNADOT_SANDBOX_NAME || "",
}