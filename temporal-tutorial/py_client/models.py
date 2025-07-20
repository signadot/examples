from dataclasses import dataclass

@dataclass
class PaymentDetails:
    from_account: str
    to_account: str
    amount: str
    reference: str = ""

@dataclass
class WithdrawRequest:
    account_id: str
    amount: str
    reference: str = ""

@dataclass
class WithdrawResponse:
    transaction_id: str
    account_id: str
    amount: str
    balance_after: str
    success: bool
    message: str

@dataclass
class DepositRequest:
    account_id: str
    amount: str
    reference: str = ""

@dataclass
class DepositResponse:
    transaction_id: str
    account_id: str
    amount: str
    balance_after: str
    success: bool
    message: str 