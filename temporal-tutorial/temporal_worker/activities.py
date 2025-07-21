import uuid
import asyncio
from decimal import Decimal
from temporalio import activity
from temporalio.exceptions import ApplicationError
from models import WithdrawRequest, WithdrawResponse, DepositRequest, DepositResponse

import logging
logger = logging.getLogger("temporal_worker.product.activities")

class BankingActivities:
    """Banking activities implementation"""
    
    @activity.defn
    async def withdraw(self, request: WithdrawRequest) -> WithdrawResponse:
        """Withdraw money from account"""
        logger.info(f"Processing withdrawal: {request.account_id}, amount: {request.amount}")
        
        # Get current balance
        current_balance = await self._get_account_balance(request.account_id)
        
        # Business logic failure - Temporal won't retry this
        if current_balance < Decimal(request.amount):
            raise ApplicationError(
                f"Insufficient funds: balance={current_balance}, requested={request.amount}",
                non_retryable=True
            )
        
        # Simulate withdrawal processing time
        await asyncio.sleep(0.5)
        
        # Generate transaction ID
        transaction_id = str(uuid.uuid4())
        
        # Calculate new balance
        new_balance = current_balance - Decimal(request.amount)
        
        # Update account balance - if this fails, Temporal will retry
        await self._update_account_balance(request.account_id, new_balance)
        
        logger.info(f"Withdrawal successful: {transaction_id}")
        
        return WithdrawResponse(
            transaction_id=transaction_id,
            account_id=request.account_id,
            amount=request.amount,
            balance_after=str(new_balance),
            success=True,
            message="Withdrawal successful"
        )
    
    @activity.defn
    async def deposit(self, request: DepositRequest) -> DepositResponse:
        """Deposit money to account"""
        logger.info(f"Processing deposit: {request.account_id}, amount: {request.amount}")
        
        # Get current balance
        current_balance = await self._get_account_balance(request.account_id)
        
        # Simulate deposit processing time
        await asyncio.sleep(0.3)
        
        # Generate transaction ID
        transaction_id = str(uuid.uuid4())
        
        # Calculate new balance
        new_balance = current_balance + Decimal(request.amount)
        
        # Update account balance - if this fails, Temporal will retry
        await self._update_account_balance(request.account_id, new_balance)
        
        logger.info(f"Deposit successful: {transaction_id}")
        
        return DepositResponse(
            transaction_id=transaction_id,
            account_id=request.account_id,
            amount=request.amount,
            balance_after=str(new_balance),
            success=True,
            message="Deposit successful"
        )
    
    async def _get_account_balance(self, account_id: str) -> Decimal:
        """Simulate getting account balance from database"""
        # In real implementation, this would query actual database
        # For demo purposes, return mock balances
        mock_balances = {
            "acc_001": Decimal('1000.00'),
            "acc_002": Decimal('500.00'),
            "acc_003": Decimal('2500.00'),
            "acc_004": Decimal('750.00')
        }
        
        # Simulate database query delay
        await asyncio.sleep(0.1)
        
        return mock_balances.get(account_id, Decimal('1000.00'))
    
    async def _update_account_balance(self, account_id: str, new_balance: Decimal):
        """Simulate updating account balance in database"""
        # In real implementation, this would update actual database
        logger.info(f"Updated balance for {account_id}: {new_balance}")
        
        # Simulate database update delay
        await asyncio.sleep(0.1)