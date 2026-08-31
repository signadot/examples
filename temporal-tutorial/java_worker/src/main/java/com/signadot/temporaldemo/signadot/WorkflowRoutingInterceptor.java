package com.signadot.temporaldemo.signadot;

import io.temporal.activity.LocalActivityOptions;
import io.temporal.api.common.v1.Payload;
import io.temporal.common.interceptors.ActivityInboundCallsInterceptor;
import io.temporal.common.interceptors.Header;
import io.temporal.common.interceptors.WorkflowInboundCallsInterceptor;
import io.temporal.common.interceptors.WorkflowInboundCallsInterceptorBase;
import io.temporal.common.interceptors.WorkflowOutboundCallsInterceptor;
import io.temporal.common.interceptors.WorkflowOutboundCallsInterceptorBase;
import io.temporal.common.interceptors.WorkerInterceptorBase;
import io.temporal.workflow.ActivityStub;
import io.temporal.workflow.Workflow;
import io.temporal.workflow.WorkflowInfo;
import org.slf4j.Logger;
import java.time.Duration;
import java.util.HashMap;
import java.util.Map;

public class WorkflowRoutingInterceptor extends WorkerInterceptorBase {
    private static final Logger logger = Workflow.getLogger(WorkflowRoutingInterceptor.class);
    private final RoutesClient routesClient;
    private final String workerIdent;

    public WorkflowRoutingInterceptor(RoutesClient routesClient, String workerIdent) {
        this.routesClient = routesClient;
        this.workerIdent = workerIdent;
    }

    @Override
    public WorkflowInboundCallsInterceptor interceptWorkflow(
        WorkflowInboundCallsInterceptor next) {
        return new WorkflowInboundCallsInterceptorBase(next) {
            private Header workflowHeader = Header.empty();

            @Override
            public void init(WorkflowOutboundCallsInterceptor outbound) {
                super.init(new WorkflowOutboundCallsInterceptorBase(outbound) {
                    // The SDK gives every outbound call a fresh empty header,
                    // so the _tracer-data routing header must be copied onto
                    // everything the workflow schedules — otherwise child
                    // workflows, continue-as-new, and (local) activities lose
                    // the routing key and fall back to the baseline worker.
                    private Header withTracerData(Header header) {
                        Payload tracerData = workflowHeader.getValues().get(OTelHeaderParsing.TRACER_DATA_HEADER);
                        if (tracerData == null) {
                            return header != null ? header : Header.empty();
                        }
                        Map<String, Payload> headers = new HashMap<>();
                        if (header != null) {
                            headers.putAll(header.getValues());
                        }
                        headers.put(OTelHeaderParsing.TRACER_DATA_HEADER, tracerData);
                        return new Header(headers);
                    }

                    @Override
                    public <R> ActivityOutput<R> executeActivity(ActivityInput<R> input) {
                        return super.executeActivity(new ActivityInput<>(
                            input.getActivityName(),
                            input.getResultClass(),
                            input.getResultType(),
                            input.getArgs(),
                            input.getOptions(),
                            withTracerData(input.getHeader())
                        ));
                    }

                    @Override
                    public <R> LocalActivityOutput<R> executeLocalActivity(LocalActivityInput<R> input) {
                        return super.executeLocalActivity(new LocalActivityInput<>(
                            input.getActivityName(),
                            input.getResultClass(),
                            input.getResultType(),
                            input.getArgs(),
                            input.getOptions(),
                            withTracerData(input.getHeader())
                        ));
                    }

                    @Override
                    public <R> ChildWorkflowOutput<R> executeChildWorkflow(ChildWorkflowInput<R> input) {
                        return super.executeChildWorkflow(new ChildWorkflowInput<>(
                            input.getWorkflowId(),
                            input.getWorkflowType(),
                            input.getResultClass(),
                            input.getResultType(),
                            input.getArgs(),
                            input.getOptions(),
                            withTracerData(input.getHeader())
                        ));
                    }

                    @Override
                    public void continueAsNew(ContinueAsNewInput input) {
                        super.continueAsNew(new ContinueAsNewInput(
                            input.getWorkflowType(),
                            input.getOptions(),
                            input.getArgs(),
                            withTracerData(input.getHeader())
                        ));
                    }

                    @Override
                    public SignalExternalOutput signalExternalWorkflow(SignalExternalInput input) {
                        return super.signalExternalWorkflow(new SignalExternalInput(
                            input.getExecution(),
                            input.getSignalName(),
                            withTracerData(input.getHeader()),
                            input.getArgs()
                        ));
                    }
                });
            }

            @Override
            public WorkflowOutput execute(WorkflowInput input) {
                workflowHeader = input.getHeader();
                String routingKey = OTelHeaderParsing.extractRoutingKeyFromHeaders(
                    workflowHeader.getValues()
                );

                // Workflow code must not read mutable process state (the
                // routes cache changes between replays), so the routing
                // decision runs as a local activity: its result is recorded
                // in history and replays see the original decision. Same
                // pattern as the Go and TypeScript workers.
                ActivityStub routingStub = Workflow.newUntypedLocalActivityStub(
                    LocalActivityOptions.newBuilder()
                        .setScheduleToCloseTimeout(Duration.ofSeconds(5))
                        .build());
                boolean shouldProcess;
                try {
                    shouldProcess = routingStub.execute("signadotShouldProcess", Boolean.class, routingKey);
                } catch (RuntimeException e) {
                    // Wrap in a plain RuntimeException: an ActivityFailure is a
                    // TemporalFailure and would fail the workflow permanently,
                    // while a plain RuntimeException fails only this workflow
                    // task, which the server retries.
                    throw new RuntimeException(String.format(
                        "Signadot routing check failed for routing key '%s' - Worker: %s",
                        routingKey, workerIdent), e);
                }

                if (!shouldProcess) {
                    String errorMsg = String.format(
                        "Workflow/Worker cannot handle routing key: %s - Worker: %s",
                        routingKey, workerIdent);
                    logger.info(errorMsg);
                    // Plain RuntimeException => workflow task failure, retried
                    // by the server until the matching worker accepts it.
                    throw new RuntimeException(errorMsg);
                }

                WorkflowInfo workflowInfo = Workflow.getInfo();
                logger.info("[Worker:{}] Workflow: {}: Processing task with routing key '{}'",
                    workerIdent, workflowInfo.getWorkflowType(), routingKey);

                return super.execute(input);
            }
        };
    }

    @Override
    public ActivityInboundCallsInterceptor interceptActivity(
        ActivityInboundCallsInterceptor next) {
        return new ActivityRoutingInterceptor(next, routesClient, workerIdent);
    }
}
