from temporalio import activity


@activity.defn
async def withdraw(account: str, amount: float) -> None:
    activity.logger.info(f"withdraw {amount} from {account}")


@activity.defn
async def deposit(account: str, amount: float) -> None:
    activity.logger.info(f"deposit {amount} to {account}")


@activity.defn
async def fraud_check(from_account: str, to_account: str, amount: float) -> None:
    activity.logger.info(f"fraud check from {from_account} to {to_account} amount {amount}")
