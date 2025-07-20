from dataclasses import dataclass
from decimal import Decimal

@dataclass
class PaymentDetails:
    """Payment request data model"""
    from_account: str
    to_account: str
    amount: str
    currency: str = "USD"
    reference: str = ""
    
    def __post_init__(self):
        if Decimal(self.amount) <= 0:
            raise ValueError("Amount must be positive")
        if not self.from_account or not self.to_account:
            raise ValueError("Account IDs cannot be empty")

@dataclass
class WithdrawRequest:
    """Withdraw activity input"""
    account_id: str
    amount: str
    reference: str = ""

@dataclass
class WithdrawResponse:
    """Withdraw activity output"""
    transaction_id: str
    account_id: str
    amount: str
    balance_after: str
    success: bool
    message: str = ""

@dataclass
class DepositRequest:
    """Deposit activity input"""
    account_id: str
    amount: str
    reference: str = ""

@dataclass
class DepositResponse:
    """Deposit activity output"""
    transaction_id: str
    account_id: str
    amount: str
    balance_after: str
    success: bool
    message: str = ""