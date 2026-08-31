package com.signadot.temporaldemo;

import com.signadot.temporaldemo.app.MoneyTransferWorkflowImpl;
import com.signadot.temporaldemo.app.BankingActivitiesImpl;
import com.signadot.temporaldemo.signadot.SandboxAwareWorkerFactory;
import io.temporal.worker.Worker;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class Main {
    private static final Logger logger = LoggerFactory.getLogger(Main.class);

    public static void main(String[] args) {
        try {
            String taskQueue = System.getenv().getOrDefault("TASK_QUEUE", "money-transfer-java");
            String temporalServerUrl = requireEnv("TEMPORAL_SERVER_URL");

            logger.info("Starting Temporal Worker");
            logger.info("Task Queue: {}", taskQueue);
            logger.info("Temporal Server: {}", temporalServerUrl);

            Worker worker = SandboxAwareWorkerFactory.createWorker(
                taskQueue,
                temporalServerUrl,
                MoneyTransferWorkflowImpl.class
            );

            worker.registerActivitiesImplementations(new BankingActivitiesImpl());

            Runtime.getRuntime().addShutdownHook(new Thread(() -> {
                logger.info("Shutdown signal received. Stopping worker...");
                SandboxAwareWorkerFactory.stopWorker(worker);
            }));

            SandboxAwareWorkerFactory.startWorker(worker);

        } catch (Exception e) {
            logger.error("Failed to start worker", e);
            System.exit(1);
        }
    }

    private static String requireEnv(String name) {
        String value = System.getenv(name);
        if (value == null || value.isEmpty()) {
            throw new IllegalStateException("Missing required environment variable: " + name);
        }
        return value;
    }
}
