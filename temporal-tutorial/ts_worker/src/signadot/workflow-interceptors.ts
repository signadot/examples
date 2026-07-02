/**
 * Workflow interceptors implementing Signadot routing-key isolation.
 * Platform-owned: registered by SandboxAwareWorker via
 * `interceptors.workflowModules`; application workflows never see them.
 *
 * These run INSIDE the deterministic V8 workflow isolate, which is the key
 * difference from the Python SDK:
 *
 * - No network, no Node.js APIs, no access to worker process memory. The
 *   isolate cannot query the routeserver directly the way the Python
 *   interceptor reads the in-process routing cache.
 *
 * - The routing decision is therefore delegated to a LOCAL ACTIVITY
 *   (`signadotShouldProcess`), which executes on the Node.js side of THIS
 *   worker with full I/O access. Its result is recorded as a marker in
 *   workflow history, so replays are deterministic: once a matching worker
 *   accepts the workflow, any later replay (e.g. baseline taking over after
 *   the sandbox is deleted) sees the recorded `true` and proceeds.
 *
 * - When the check says "not mine", we throw a plain Error. In the TypeScript
 *   SDK, any error that is not a TemporalFailure fails the WORKFLOW TASK (not
 *   the workflow), so the server retries the task until a worker that matches
 *   the routing key polls it. Commands from the failed task -- including the
 *   local activity marker -- are discarded, so the next worker re-runs its own
 *   routing check.
 *
 * - The OTel context header (`_tracer-data`, carrying the routing key in W3C
 *   baggage) is propagated from the workflow to everything the workflow
 *   schedules by copying the payload verbatim in the outbound interceptor.
 *   This is a pure, deterministic string copy -- deliberately NOT the OTel SDK
 *   propagators: keeping OpenTelemetry runtime state out of the workflow
 *   isolate avoids depending on mutable module state inside the shared V8
 *   context, which must be identical across replays.
 */
import {
  proxyLocalActivities,
  WorkflowInterceptors,
  WorkflowInterceptorsFactory,
  WorkflowInboundCallsInterceptor,
  WorkflowOutboundCallsInterceptor,
  WorkflowExecuteInput,
  ActivityInput,
  LocalActivityInput,
  StartChildWorkflowExecutionInput,
  ContinueAsNewInput,
  SignalWorkflowInput,
  workflowInfo,
} from '@temporalio/workflow';
import type { Next, Headers } from '@temporalio/workflow';
import type { Payload } from '@temporalio/common';
import { TRACE_HEADER, routingKeyFromHeaders } from './tracer-headers';

/** Tracer-data payload captured from the workflow start headers. */
interface TracerHeaderState {
  payload?: Payload;
}

class SignadotWorkflowInboundInterceptor implements WorkflowInboundCallsInterceptor {
  private readonly signadotShouldProcess: (routingKey: string) => Promise<boolean>;

  constructor(private readonly state: TracerHeaderState) {
    const { signadotShouldProcess } = proxyLocalActivities<{
      signadotShouldProcess(routingKey: string): Promise<boolean>;
    }>({
      startToCloseTimeout: '10 seconds',
      retry: { maximumAttempts: 3 },
    });
    this.signadotShouldProcess = signadotShouldProcess;
  }

  async execute(input: WorkflowExecuteInput, next: Next<WorkflowInboundCallsInterceptor, 'execute'>): Promise<unknown> {
    // Capture the OTel context header so the outbound interceptor can stamp it
    // onto activities/child workflows scheduled by this workflow.
    this.state.payload = input.headers[TRACE_HEADER];

    const routingKey = routingKeyFromHeaders(input.headers);
    let shouldProcess: boolean;
    try {
      shouldProcess = await this.signadotShouldProcess(routingKey);
    } catch (err) {
      // Never let a failed routing check fail the workflow itself: convert to
      // a plain Error so it only fails this workflow task and gets retried.
      throw new Error(`Signadot routing check failed for routing key '${routingKey}': ${err}`);
    }
    if (!shouldProcess) {
      throw new Error(
        `Workflow/Worker cannot handle routing key: '${routingKey}' - Workflow: ${workflowInfo().workflowType}`
      );
    }
    return next(input);
  }
}

/**
 * Copies the `_tracer-data` header from the workflow start headers onto
 * everything the workflow schedules, so:
 * - the activity-level routing check on the Node.js side sees the routing key,
 * - the OTel activity interceptor can restore the context (baggage included)
 *   around activity execution for downstream HTTP propagation,
 * - child workflows / continue-as-new carry the routing key forward.
 */
class SignadotWorkflowOutboundInterceptor implements WorkflowOutboundCallsInterceptor {
  constructor(private readonly state: TracerHeaderState) {}

  private withTracerHeader(headers: Headers): Headers {
    if (this.state.payload === undefined || headers[TRACE_HEADER] !== undefined) {
      return headers;
    }
    return { ...headers, [TRACE_HEADER]: this.state.payload };
  }

  scheduleActivity(input: ActivityInput, next: Next<WorkflowOutboundCallsInterceptor, 'scheduleActivity'>): Promise<unknown> {
    return next({ ...input, headers: this.withTracerHeader(input.headers) });
  }

  scheduleLocalActivity(
    input: LocalActivityInput,
    next: Next<WorkflowOutboundCallsInterceptor, 'scheduleLocalActivity'>
  ): Promise<unknown> {
    return next({ ...input, headers: this.withTracerHeader(input.headers) });
  }

  startChildWorkflowExecution(
    input: StartChildWorkflowExecutionInput,
    next: Next<WorkflowOutboundCallsInterceptor, 'startChildWorkflowExecution'>
  ): Promise<[Promise<string>, Promise<unknown>]> {
    return next({ ...input, headers: this.withTracerHeader(input.headers) });
  }

  continueAsNew(input: ContinueAsNewInput, next: Next<WorkflowOutboundCallsInterceptor, 'continueAsNew'>): Promise<never> {
    return next({ ...input, headers: this.withTracerHeader(input.headers) });
  }

  signalWorkflow(input: SignalWorkflowInput, next: Next<WorkflowOutboundCallsInterceptor, 'signalWorkflow'>): Promise<void> {
    return next({ ...input, headers: this.withTracerHeader(input.headers) });
  }
}

export const interceptors: WorkflowInterceptorsFactory = (): WorkflowInterceptors => {
  // Shared per-workflow-run state; repopulated deterministically on replay.
  const state: TracerHeaderState = {};
  return {
    inbound: [new SignadotWorkflowInboundInterceptor(state)],
    outbound: [new SignadotWorkflowOutboundInterceptor(state)],
  };
};
