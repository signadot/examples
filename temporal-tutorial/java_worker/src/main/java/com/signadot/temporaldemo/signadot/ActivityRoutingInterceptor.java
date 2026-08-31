package com.signadot.temporaldemo.signadot;

import io.opentelemetry.api.baggage.propagation.W3CBaggagePropagator;
import io.opentelemetry.api.trace.propagation.W3CTraceContextPropagator;
import io.opentelemetry.context.Context;
import io.opentelemetry.context.Scope;
import io.opentelemetry.context.propagation.TextMapGetter;
import io.temporal.activity.ActivityExecutionContext;
import io.temporal.common.interceptors.ActivityInboundCallsInterceptor;
import io.temporal.common.interceptors.ActivityInboundCallsInterceptorBase;
import io.temporal.failure.ApplicationFailure;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import java.time.Duration;
import java.util.Map;

public class ActivityRoutingInterceptor extends ActivityInboundCallsInterceptorBase {
    private static final Logger logger = LoggerFactory.getLogger(ActivityRoutingInterceptor.class);

    private static final TextMapGetter<Map<String, String>> CARRIER_GETTER =
        new TextMapGetter<>() {
            @Override
            public Iterable<String> keys(Map<String, String> carrier) {
                return carrier.keySet();
            }

            @Override
            public String get(Map<String, String> carrier, String key) {
                return carrier == null ? null : carrier.get(key);
            }
        };

    private final RoutesClient routesClient;
    private final String workerIdent;
    private ActivityExecutionContext activityContext;

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
        this.activityContext = context;
        super.init(context);
    }

    @Override
    public ActivityOutput execute(ActivityInput input) {
        // Local activities always run on the worker that is executing the
        // workflow task and are retried on that same worker. A routing
        // rejection cannot migrate them elsewhere, so skip the check
        // (the Go and TypeScript workers do the same).
        boolean isLocal = activityContext != null && activityContext.getInfo().isLocal();

        Map<String, String> carrier = OTelHeaderParsing.extractCarrier(
            input.getHeader() != null ? input.getHeader().getValues() : null);
        String routingKey = OTelHeaderParsing.routingKeyFromCarrier(carrier);

        if (!isLocal) {
            if (!routesClient.shouldProcess(routingKey)) {
                String errorMsg = String.format(
                    "Activity/Worker cannot handle routing key: %s - Worker: %s",
                    routingKey, workerIdent);
                logger.info(errorMsg);
                // Retryable by design: the server redelivers until the right
                // worker claims the task. The 1s next-retry delay keeps
                // wrong-worker bounces fast instead of following the app's
                // backoff curve.
                throw ApplicationFailure.newFailureWithCauseAndDelay(
                    errorMsg, "RoutingKeyNotHandled", null, Duration.ofSeconds(1));
            }

            logger.info("[Worker:{}] Activity: Processing task with routing key '{}'",
                workerIdent, routingKey);
        }

        if (carrier == null) {
            return super.execute(input);
        }

        // Restore the full OTel context (trace context plus ALL baggage
        // members, not just the routing key) around the activity, so outbound
        // calls made with an OTel-instrumented HTTP client carry
        // `baggage: sd-routing-key=...` plus trace correlation downstream.
        Context otelContext = W3CBaggagePropagator.getInstance().extract(
            W3CTraceContextPropagator.getInstance().extract(Context.root(), carrier, CARRIER_GETTER),
            carrier, CARRIER_GETTER);
        try (Scope ignored = otelContext.makeCurrent()) {
            return super.execute(input);
        }
    }
}
