from temporalio import activity


@activity.defn
async def withdraw(account: str, amount: float) -> None:
    activity.logger.info(f"withdraw {amount} from {account}")


@activity.defn
async def deposit(account: str, amount: float) -> None:
    activity.logger.info(f"deposit {amount} to {account}")
