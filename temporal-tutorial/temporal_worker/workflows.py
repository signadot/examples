from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError
from models import PaymentDetails, WithdrawRequest, DepositRequest
from activities import BankingActivities

import logging
logger = logging.getLogger("temporal_worker.product.workflows")

# Common retry policy for banking activities
COMMON_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    maximum_attempts=10,
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=10)
)

@workflow.defn
class MoneyTransferWorkflow:
    """Baseline money transfer workflow - 2 step process"""
    
    @workflow.run
    async def run(self, payment_details: PaymentDetails) -> str:
        """Execute money transfer workflow"""
        logger.info(f"Starting money transfer: {payment_details.from_account} -> {payment_details.to_account}, amount: {payment_details.amount}")
        
        # Step 1: Withdraw money from source account
        withdraw_request = WithdrawRequest(
            account_id=payment_details.from_account,
            amount=payment_details.amount,
            reference=payment_details.reference
        )
        
        withdraw_result = await workflow.execute_activity(
            BankingActivities.withdraw,
            withdraw_request,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=COMMON_RETRY_POLICY
        )
        
        logger.info(f"Withdrawal successful: {withdraw_result.transaction_id}")
        
        # Step 2: Deposit money to destination account
        deposit_request = DepositRequest(
            account_id=payment_details.to_account,
            amount=payment_details.amount,
            reference=payment_details.reference
        )
        
        deposit_result = await workflow.execute_activity(
            BankingActivities.deposit,
            deposit_request,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=COMMON_RETRY_POLICY
        )
        
        logger.info(f"Deposit successful: {deposit_result.transaction_id}")
        logger.info(f"Money transfer completed successfully")
        
        return f"Transfer complete: {withdraw_result.transaction_id} -> {deposit_result.transaction_id}"