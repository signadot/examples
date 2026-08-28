package com.signadot.temporaldemo.app;

import io.temporal.activity.ActivityInterface;
import io.temporal.activity.ActivityMethod;

@ActivityInterface
public interface BankingActivities {
    @ActivityMethod
    WithdrawResponse withdraw(WithdrawRequest request);

    @ActivityMethod
    DepositResponse deposit(DepositRequest request);
}
