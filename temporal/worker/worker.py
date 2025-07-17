import asyncio
import os

from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.contrib.opentelemetry import TracingInterceptor

from ..platform.route_server import RouteServerClient
from ..platform.interceptors import RoutingWorkflowInterceptor, RoutingActivityInterceptor
from .workflow import BankTransferWorkflow
from . import activities


async def main() -> None:
    server = os.getenv("TEMPORAL_SERVER", "temporal-frontend.temporal.svc:7233")
    task_queue = os.getenv("TASK_QUEUE", "bank-transfer")
    sandbox = os.getenv("SANDBOX_NAME", "")
    route_server = os.getenv("ROUTE_SERVER", "routeserver.default.svc:3000")

    router = RouteServerClient(route_server, "Deployment", "temporal-demo", "worker", sandbox)
    asyncio.create_task(router.run())

    client = await Client.connect(server, interceptors=[TracingInterceptor()])

    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=[BankTransferWorkflow],
        activities=[activities.withdraw, activities.deposit],
        interceptors=[
            TracingInterceptor(),
            lambda next: RoutingWorkflowInterceptor(next, router),
            lambda next: RoutingActivityInterceptor(next, router),
        ],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
