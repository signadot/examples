
module.exports = {
    // Ports
    frontendPort: process.env.FRONTEND_PORT || 4000,
    producerPort: process.env.PRODUCER_PORT || 4001,

    // Addresses
    producerHost: process.env.PRODUCER_HOST || "publisher.pubsub-demo.svc",
    redisURL: process.env.REDIS_URL || "redis://redis.pubsub-demo.svc:6379",
    routeServerAddr: "routeserver.signadot.svc:7778",

    // Baseline
    baselineKind: process.env.BASELINE_KIND || "Deployment",
    baselineNamespace: process.env.BASELINE_NAMESPACE || "pubsub-demo",
    baselineName: process.env.BASELINE_NAME || "",

    // Sandbox
    sandboxName: process.env.SIGNADOT_SANDBOX_NAME || "",

    pubsubTopic: process.env.PUBSUB_TOPIC || "pubsub-demo"
}