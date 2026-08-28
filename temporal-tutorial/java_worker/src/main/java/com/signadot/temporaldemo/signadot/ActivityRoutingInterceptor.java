package com.signadot.temporaldemo.signadot;

import io.opentelemetry.api.baggage.Baggage;
import io.opentelemetry.context.Context;
import io.opentelemetry.context.Scope;
import io.temporal.activity.ActivityExecutionContext;
import io.temporal.common.interceptors.ActivityInboundCallsInterceptor;
import io.temporal.common.interceptors.ActivityInboundCallsInterceptorBase;
import io.temporal.failure.ApplicationFailure;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

// ENG-REVIEW: verify ActivityInboundCallsInterceptorBase is the correct base
// class for wrapping `next` in temporal-sdk 1.30.x.
public class ActivityRoutingInterceptor extends ActivityInboundCallsInterceptorBase {
    private static final Logger logger = LoggerFactory.getLogger(ActivityRoutingInterceptor.class);
    private static final String SD_ROUTING_KEY = "sd-routing-key";

    private final RoutesClient routesClient;
    private final String workerIdent;

    public ActivityRoutingInterceptor(
        ActivityInboundCallsInterceptor next,
        RoutesClient routesClient,
        String workerIdent) {
        super(next);
        this.routesClient = routesClient;
        this.workerIdent = workerIdent;
    }

    @Override
    public void init(ActivityExecutionContext context) {
        super.init(context);
    }

    @Override
    public ActivityOutput execute(ActivityInput input) {
        // ENG-REVIEW: verify ActivityInput exposes the header map as
        // getHeader().getValues() (Map<String, Payload>) in temporal-sdk 1.30.x.
        String routingKey = OTelHeaderParsing.extractRoutingKeyFromHeaders(input.getHeader().getValues());

        if (!routesClient.shouldProcess(routingKey)) {
            String errorMsg = String.format(
                "Activity/Worker cannot handle routing key: %s - Worker: %s",
                routingKey, workerIdent);
            logger.info(errorMsg);
            // Retryable by design: the server redelivers until the right worker
            // claims the task.
            // ENG-REVIEW: set nextRetryDelay (~1s) on this failure so wrong-worker
            // bounces skip exponential backoff; confirm the 1.30.x API for it
            // (ApplicationFailure builder vs newFailureWithCause overloads).
            throw ApplicationFailure.newFailure(errorMsg, "RoutingKeyNotHandled");
        }

        logger.info("[Worker:{}] Activity: Processing task with routing key '{}'",
            workerIdent, routingKey);

        if (routingKey.isEmpty()) {
            return super.execute(input);
        }

        // Bridge the routing key into OTel Baggage for the duration of the
        // activity, so outbound HTTP calls made by activity code carry
        // `baggage: sd-routing-key=...` and route correctly downstream. The
        // SDK's tracing interceptors do not do this for activities on their own.
        Baggage baggage = Baggage.builder().put(SD_ROUTING_KEY, routingKey).build();
        Context otelContext = Context.current().with(baggage);
        try (Scope ignored = otelContext.makeCurrent()) {
            return super.execute(input);
        }
    }
}
