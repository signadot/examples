import os
import uuid
from typing import Dict

from temporalio.client import Client
from temporalio.contrib.opentelemetry import TracingInterceptor
from models import PaymentDetails

async def start_workflow_with_routing(payment_details: PaymentDetails) -> Dict:
    """
    Starts the MoneyTransferWorkflow with OpenTelemetry context propagation.
    """
    temporal_server_url = os.getenv("TEMPORAL_SERVER_URL", "temporal.temporal:7233")
    
    # Connect with TracingInterceptor for OTel context propagation
    client = await Client.connect(
        temporal_server_url,
        interceptors=[TracingInterceptor()]
    )
    
    workflow_id = f"money-transfer-{uuid.uuid4()}"
    handle = await client.start_workflow(
        "MoneyTransferWorkflow",
        payment_details,
        id=workflow_id,
        task_queue="money-transfer"
    )
    
    return {
        "message": f"Started workflow with ID: {handle.id}, Run ID: {handle.result_run_id}",
        "workflow_id": handle.id,
        "run_id": handle.result_run_id
    } 