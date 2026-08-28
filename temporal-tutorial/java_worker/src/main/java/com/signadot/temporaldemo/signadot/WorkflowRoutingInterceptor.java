package com.signadot.temporaldemo.signadot;

import io.temporal.api.common.v1.Payload;
import io.temporal.common.interceptors.ActivityInboundCallsInterceptor;
import io.temporal.common.interceptors.Header;
import io.temporal.common.interceptors.WorkflowInboundCallsInterceptor;
import io.temporal.common.interceptors.WorkflowInboundCallsInterceptorBase;
import io.temporal.common.interceptors.WorkflowOutboundCallsInterceptor;
import io.temporal.common.interceptors.WorkflowOutboundCallsInterceptorBase;
import io.temporal.common.interceptors.WorkerInterceptorBase;
import io.temporal.workflow.Workflow;
import io.temporal.workflow.WorkflowInfo;
import org.slf4j.Logger;
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
                    @Override
                    public <R> ActivityOutput<R> executeActivity(ActivityInput<R> input) {
                        Map<String, Payload> headers = new HashMap<>();
                        if (input.getHeader() != null) {
                            headers.putAll(input.getHeader().getValues());
                        }
                        Payload tracerData = workflowHeader.getValues().get("_tracer-data");
                        if (tracerData != null) {
                            headers.put("_tracer-data", tracerData);
                        }

                        ActivityInput<R> propagated = new ActivityInput<>(
                            input.getActivityName(),
                            input.getResultClass(),
                            input.getResultType(),
                            input.getArgs(),
                            input.getOptions(),
                            new Header(headers)
                        );
                        return super.executeActivity(propagated);
                    }
                });
            }

            @Override
            public WorkflowOutput execute(WorkflowInput input) {
                workflowHeader = input.getHeader();
                String routingKey = OTelHeaderParsing.extractRoutingKeyFromHeaders(
                    workflowHeader.getValues()
                );

                // ENG-REVIEW design fork: this reads the routes cache directly
                // from the workflow thread, mirroring the Python implementation
                // (in-memory volatile read, no I/O). The TypeScript worker instead
                // consults the routeserver via a local activity so the decision is
                // recorded in history and replay-stable. Pick the pattern Java
                // should standardize on; if replay stability matters here, switch
                // to a local activity stub.
                if (!routesClient.shouldProcess(routingKey)) {
                    String errorMsg = String.format(
                        "Workflow/Worker cannot handle routing key: %s - Worker: %s",
                        routingKey, workerIdent);
                    logger.info(errorMsg);
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
