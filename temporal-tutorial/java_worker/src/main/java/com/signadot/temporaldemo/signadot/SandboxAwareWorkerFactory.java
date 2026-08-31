package com.signadot.temporaldemo.signadot;

import io.temporal.client.WorkflowClient;
import io.temporal.client.WorkflowClientOptions;
import io.temporal.serviceclient.WorkflowServiceStubs;
import io.temporal.serviceclient.WorkflowServiceStubsOptions;
import io.temporal.worker.Worker;
import io.temporal.worker.WorkerFactory;
import io.temporal.worker.WorkerFactoryOptions;
import io.temporal.worker.WorkerOptions;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;

public class SandboxAwareWorkerFactory {
    private static final Logger logger = LoggerFactory.getLogger(SandboxAwareWorkerFactory.class);
    private static final Map<Worker, WorkerResources> resourcesByWorker = new ConcurrentHashMap<>();

    private record WorkerResources(
        WorkerFactory factory,
        WorkflowServiceStubs serviceStubs,
        RoutesClient routesClient) {}

    public static Worker createWorker(
        String taskQueue,
        String temporalServerUrl,
        Class<?>... workflowClasses) {

        String sandboxName = System.getenv().getOrDefault("SIGNADOT_SANDBOX_NAME", "");
        RoutesClient routesClient = new RoutesClient(sandboxName);
        String workerIdent = String.format("sandbox=%s task_queue=%s",
            sandboxName.isEmpty() ? "baseline" : sandboxName, taskQueue);

        routesClient.startPolling();

        WorkflowServiceStubs serviceStubs = WorkflowServiceStubs.newServiceStubs(
            WorkflowServiceStubsOptions.newBuilder()
                .setTarget(temporalServerUrl)
                .build()
        );

        WorkflowClient workflowClient = WorkflowClient.newInstance(serviceStubs);

        WorkerFactoryOptions factoryOptions = WorkerFactoryOptions.newBuilder()
            .setWorkerInterceptors(new WorkflowRoutingInterceptor(routesClient, workerIdent))
            .build();
        WorkerFactory workerFactory = WorkerFactory.newInstance(workflowClient, factoryOptions);

        Worker worker = workerFactory.newWorker(taskQueue, WorkerOptions.newBuilder().build());

        for (Class<?> workflowClass : workflowClasses) {
            worker.registerWorkflowImplementationTypes(workflowClass);
        }

        // Platform-provided local activity used by the workflow routing check
        worker.registerActivitiesImplementations(
            new SignadotRoutingActivitiesImpl(routesClient, workerIdent));

        logger.info("Worker created successfully: {}", workerIdent);
        resourcesByWorker.put(worker, new WorkerResources(workerFactory, serviceStubs, routesClient));

        return worker;
    }

    public static void startWorker(Worker worker) {
        logger.info("Starting to poll for tasks...");
        requireResources(worker).factory().start();
    }

    public static void stopWorker(Worker worker) {
        if (worker != null) {
            WorkerResources resources = resourcesByWorker.remove(worker);
            if (resources != null) {
                resources.factory().shutdown();
                resources.factory().awaitTermination(10, TimeUnit.SECONDS);
                resources.routesClient().stopPolling();
                resources.serviceStubs().shutdown();
            }
        }
    }

    private static WorkerResources requireResources(Worker worker) {
        WorkerResources resources = resourcesByWorker.get(worker);
        if (resources == null) {
            throw new IllegalStateException("Worker was not created by SandboxAwareWorkerFactory");
        }
        return resources;
    }
}
