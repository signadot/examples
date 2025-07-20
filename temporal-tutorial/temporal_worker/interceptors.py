import json
import logging
import os
import sys
from temporalio.worker import Interceptor
from temporalio.worker._interceptor import (
    ExecuteActivityInput,
    ExecuteWorkflowInput,
    WorkflowInboundInterceptor,
    ActivityInboundInterceptor,
    WorkflowInterceptorClassInput
)
from opentelemetry import baggage
from routing import RoutesAPIClient

ROUTING_KEY = "sd-routing-key"
logger = logging.getLogger("temporal_worker.interceptors")

class SelectiveTaskInterceptor(Interceptor):
    """
    Interceptor for selective processing of workflows and activities based on routing keys.
    Uses RoutesAPIClient to determine if a task should be processed.
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
                routing_key = baggage.get_baggage(ROUTING_KEY) or ""
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
            
            def _extract_routing_key_from_headers(self, input: ExecuteActivityInput) -> str:
                try:
                    if hasattr(input, 'headers') and input.headers:
                        tracer_data = input.headers.get('_tracer-data')
                        if tracer_data and hasattr(tracer_data, 'data'):
                            data = json.loads(tracer_data.data)
                            if 'baggage' in data:
                                baggage_str = data['baggage']
                                for item in baggage_str.split(','):
                                    if item.strip().startswith('sd-routing-key='):
                                        return item.split('=', 1)[1]
                except Exception as e:
                    logger.error(f"[ActivityDebug] Failed to extract routing key: {e}")
                return ""
            
            async def execute_activity(self, input: ExecuteActivityInput):
                routing_key = self._extract_routing_key_from_headers(input)
                activity_name = getattr(input.fn, "__name__", str(input.fn))
                should_process = True
                
                if self.routes_client and not await self.routes_client.should_process(routing_key):
                    should_process = False
                
                if not should_process:
                    error_msg = f"Activity/Worker cannot handle routing key: {routing_key} - Worker: {self.worker_ident}"
                    logger.info(error_msg)
                    raise Exception(error_msg)

                logger.info(f"[Worker:{self.worker_ident}] Activity: {activity_name}: Processing task with routing key '{routing_key}'")
                return await self.next.execute_activity(input)

        return _SelectiveActivityInboundInterceptor(next)
