"""
Worker interceptors implementing Signadot routing-key isolation.

Platform-owned: application workflows and activities never interact with this
module directly -- it is wired up by SandboxAwareWorker (see worker.py).
"""
import logging
from typing import Mapping, Optional

import temporalio.api.common.v1
import temporalio.converter
from temporalio.worker import Interceptor
from temporalio.worker._interceptor import (
    ExecuteActivityInput,
    ExecuteWorkflowInput,
    WorkflowInboundInterceptor,
    ActivityInboundInterceptor,
    WorkflowInterceptorClassInput
)
from opentelemetry import baggage, propagate
from opentelemetry import context as otel_context
from temporalio.contrib.opentelemetry import default_text_map_propagator

from .routing import RoutesAPIClient

ROUTING_KEY = "sd-routing-key"
# Header key used by the Temporal OpenTelemetry interceptors (same key in the
# Python, TypeScript, and Java SDKs, so headers are cross-SDK compatible).
TRACE_HEADER_KEY = "_tracer-data"
logger = logging.getLogger("temporal_worker.signadot.interceptors")


def outbound_http_headers() -> dict:
    """
    Headers that an outbound HTTP call made from the current context would
    carry (e.g. `traceparent` and `baggage: sd-routing-key=...`).

    Instrumented HTTP clients (SandboxAwareWorker instruments aiohttp; use
    opentelemetry-instrumentation-requests/-httpx for others) inject these
    automatically. Call this only for clients without instrumentation and pass
    the result as request headers.
    """
    headers: dict = {}
    propagate.inject(headers)
    return headers


def context_from_headers(
    headers: Mapping[str, temporalio.api.common.v1.Payload],
) -> Optional[otel_context.Context]:
    """
    Deserialize the OpenTelemetry context (trace context + baggage) that the
    TracingInterceptor stored in the Temporal headers under `_tracer-data`.
    """
    payload = headers.get(TRACE_HEADER_KEY)
    if not payload:
        return None
    try:
        carrier = temporalio.converter.PayloadConverter.default.from_payloads([payload])[0]
        if not carrier:
            return None
        return default_text_map_propagator.extract(carrier)
    except Exception as e:
        logger.error(f"Failed to extract OTel context from Temporal headers: {e}")
        return None


def routing_key_from_context(context: Optional[otel_context.Context]) -> str:
    """Read the Signadot routing key from baggage stored in the given context."""
    if context is None:
        return ""
    return str(baggage.get_baggage(ROUTING_KEY, context) or "")


class SelectiveTaskInterceptor(Interceptor):
    """
    Interceptor for selective processing of workflows and activities based on routing keys.
    Uses RoutesAPIClient to determine if a task should be processed.

    For activities, it also bridges the baggage stored in the task headers into
    the current OpenTelemetry context for the duration of the activity, so that
    any outbound HTTP calls made from within the activity automatically carry
    the `sd-routing-key` baggage header and get routed correctly downstream.
    """
    def __init__(self, routes_client: RoutesAPIClient, sandbox_name: str, task_queue: str):
        super().__init__()
        self.sandbox_name = sandbox_name
        self.task_queue = task_queue
        self.routes_client = routes_client
        # Worker identity constructed from passed parameters
        self.worker_ident = f"sandbox={sandbox_name or 'baseline'} task_queue={task_queue}"

    def workflow_interceptor_class(self, input: WorkflowInterceptorClassInput):
        outer_self = self
        class _SelectiveWorkflowInboundInterceptor(WorkflowInboundInterceptor):
            def __init__(self, next_interceptor):
                super().__init__(next_interceptor)
                self.routes_client = outer_self.routes_client
                self.sandbox_name = outer_self.sandbox_name
                self.worker_ident = outer_self.worker_ident

            async def execute_workflow(self, input: ExecuteWorkflowInput):
                # The TracingInterceptor (registered before this interceptor) has
                # already attached the OTel context from the workflow headers, so
                # baggage is readable directly here.
                routing_key = str(baggage.get_baggage(ROUTING_KEY) or "")
                workflow_name = getattr(input.run_fn, "__name__", str(input.run_fn))
                should_process = True

                if self.routes_client and not await self.routes_client.should_process(routing_key):
                    should_process = False

                if not should_process:
                    error_msg = f"Workflow/Worker cannot handle routing key: {routing_key} - Worker: {self.worker_ident}"
                    logger.info(error_msg)
                    raise Exception(error_msg)

                logger.info(f"[Worker:{self.worker_ident}] Workflow: {workflow_name}: Processing task with routing key '{routing_key}'")
                return await self.next.execute_workflow(input)

        return _SelectiveWorkflowInboundInterceptor

    def intercept_activity(self, next: ActivityInboundInterceptor) -> ActivityInboundInterceptor:
        outer_self = self
        class _SelectiveActivityInboundInterceptor(ActivityInboundInterceptor):
            def __init__(self, next_interceptor):
                super().__init__(next_interceptor)
                self.routes_client = outer_self.routes_client
                self.sandbox_name = outer_self.sandbox_name
                self.worker_ident = outer_self.worker_ident

            async def execute_activity(self, input: ExecuteActivityInput):
                # Unlike workflows, the SDK's TracingInterceptor only uses the
                # context from the headers to parent the activity span -- it does
                # NOT attach it, so baggage is not available via get_baggage()
                # here. Extract it from the headers explicitly instead.
                header_context = context_from_headers(input.headers)
                routing_key = routing_key_from_context(header_context)
                activity_name = getattr(input.fn, "__name__", str(input.fn))
                should_process = True

                if self.routes_client and not await self.routes_client.should_process(routing_key):
                    should_process = False

                if not should_process:
                    error_msg = f"Activity/Worker cannot handle routing key: {routing_key} - Worker: {self.worker_ident}"
                    logger.info(error_msg)
                    raise Exception(error_msg)

                logger.info(f"[Worker:{self.worker_ident}] Activity: {activity_name}: Processing task with routing key '{routing_key}'")

                # Bridge baggage from the task headers into the current OTel
                # context, scoped to this activity execution. Without this,
                # outbound HTTP calls made by the activity would carry the trace
                # context but NOT the sd-routing-key baggage, so downstream
                # services would not route sandbox traffic correctly.
                context = otel_context.get_current()
                if header_context is not None:
                    for key, value in baggage.get_all(header_context).items():
                        context = baggage.set_baggage(key, value, context=context)
                token = otel_context.attach(context)
                try:
                    logger.info(
                        f"[Worker:{self.worker_ident}] Activity: {activity_name}: outbound HTTP calls will carry: {outbound_http_headers()}"
                    )
                    return await self.next.execute_activity(input)
                finally:
                    otel_context.detach(token)

        return _SelectiveActivityInboundInterceptor(next)
