import logging_config  # global logging config must be first
import os
import asyncio
from sandbox_aware_worker import SandboxAwareWorker
from workflows import MoneyTransferWorkflow
from activities import BankingActivities

async def main():
    # Get task queue from environment
    task_queue = os.environ["TASK_QUEUE"]
    
    # Create banking activities instance
    banking_activities = BankingActivities()
    
    # Create the SandboxAware worker
    worker = SandboxAwareWorker(
        task_queue=task_queue,
        workflows=[MoneyTransferWorkflow],
        activities=[
            banking_activities.withdraw,
            banking_activities.deposit,
        ]
    )
    
    # Start the worker
    await worker.start()

if __name__ == "__main__":
    asyncio.run(main())