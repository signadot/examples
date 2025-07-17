from temporalio.contrib.opentelemetry import TracingInterceptor
from temporalio.worker import WorkflowInboundInterceptor, ActivityInboundInterceptor
from temporalio import exceptions
from opentelemetry import baggage


class RoutingWorkflowInterceptor(WorkflowInboundInterceptor):
    """Interceptor that decides whether to run a workflow based on routing key."""

    def __init__(self, next, router):
        super().__init__(next)
        self.router = router

    async def execute_workflow(self, input):
        routing_key = baggage.get_baggage("sd-routing-key") or ""
        if not self.router.should_process(routing_key):
            raise exceptions.ApplicationError("routing key rejected", non_retryable=True)
        return await self.next.execute_workflow(input)


class RoutingActivityInterceptor(ActivityInboundInterceptor):
    """Interceptor that skips activity execution when routing key mismatches."""

    def __init__(self, next, router):
        super().__init__(next)
        self.router = router

    async def execute_activity(self, input):
        routing_key = baggage.get_baggage("sd-routing-key") or ""
        if not self.router.should_process(routing_key):
            raise exceptions.ApplicationError("routing key rejected", non_retryable=True)
        return await self.next.execute_activity(input)
