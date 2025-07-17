from temporalio import workflow
from . import activities


@workflow.defn
class BankTransferWorkflowV2:
    @workflow.run
    async def run(self, from_account: str, to_account: str, amount: float) -> None:
        await workflow.execute_activity(
            activities.fraud_check,
            from_account,
            to_account,
            amount,
            schedule_to_close_timeout=5,
        )
        await workflow.execute_activity(
            activities.withdraw,
            from_account,
            amount,
            schedule_to_close_timeout=5,
        )
        await workflow.execute_activity(
            activities.deposit,
            to_account,
            amount,
            schedule_to_close_timeout=5,
        )
