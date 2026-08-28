package com.signadot.temporaldemo.app;

import io.temporal.workflow.Workflow;
import io.temporal.common.RetryOptions;
import java.time.Duration;
import org.slf4j.Logger;

public class MoneyTransferWorkflowImpl implements MoneyTransferWorkflow {
    private static final Logger logger = Workflow.getLogger(MoneyTransferWorkflowImpl.class);

    private final BankingActivities activities = Workflow.newActivityStub(
        BankingActivities.class,
        io.temporal.activity.ActivityOptions.newBuilder()
            .setStartToCloseTimeout(Duration.ofSeconds(30))
            .setRetryOptions(RetryOptions.newBuilder()
                .setInitialInterval(Duration.ofSeconds(5))
                .setMaximumAttempts(10)
                .setBackoffCoefficient(2.0)
                .setMaximumInterval(Duration.ofSeconds(10))
                .build())
            .build()
    );

    @Override
    public String run(PaymentDetails paymentDetails) {
        logger.info("Starting money transfer: {} -> {}, amount: {}",
            paymentDetails.getFromAccount(),
            paymentDetails.getToAccount(),
            paymentDetails.getAmount());

        WithdrawRequest withdrawRequest = new WithdrawRequest(
            paymentDetails.getFromAccount(),
            paymentDetails.getAmount(),
            paymentDetails.getReference()
        );

        WithdrawResponse withdrawResult = activities.withdraw(withdrawRequest);
        logger.info("Withdrawal successful: {}", withdrawResult.getTransactionId());

        DepositRequest depositRequest = new DepositRequest(
            paymentDetails.getToAccount(),
            paymentDetails.getAmount(),
            paymentDetails.getReference()
        );

        DepositResponse depositResult = activities.deposit(depositRequest);
        logger.info("Deposit successful: {}", depositResult.getTransactionId());
        logger.info("Money transfer completed successfully");

        return String.format("Transfer complete: %s -> %s",
            withdrawResult.getTransactionId(),
            depositResult.getTransactionId());
    }
}
