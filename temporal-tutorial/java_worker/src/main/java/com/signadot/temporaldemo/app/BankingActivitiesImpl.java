package com.signadot.temporaldemo.app;

import io.temporal.failure.ApplicationFailure;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import java.math.BigDecimal;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

public class BankingActivitiesImpl implements BankingActivities {
    private static final Logger logger = LoggerFactory.getLogger(BankingActivitiesImpl.class);

    private static final Map<String, BigDecimal> mockBalances = new HashMap<>();

    static {
        mockBalances.put("acc_001", new BigDecimal("1000.00"));
        mockBalances.put("acc_002", new BigDecimal("500.00"));
        mockBalances.put("acc_003", new BigDecimal("2500.00"));
        mockBalances.put("acc_004", new BigDecimal("750.00"));
    }

    @Override
    public WithdrawResponse withdraw(WithdrawRequest request) {
        logger.info("Processing withdrawal: {}, amount: {}", request.getAccountId(), request.getAmount());

        BigDecimal currentBalance = getAccountBalance(request.getAccountId());
        BigDecimal amount = new BigDecimal(request.getAmount());

        if (currentBalance.compareTo(amount) < 0) {
            // Non-retryable: a deterministic business failure would produce
            // the same result on every retry.
            throw ApplicationFailure.newNonRetryableFailure(
                String.format("Insufficient funds: balance=%s, requested=%s", currentBalance, amount),
                "InsufficientFunds"
            );
        }

        sleep(500);

        String transactionId = UUID.randomUUID().toString();
        BigDecimal newBalance = currentBalance.subtract(amount);
        updateAccountBalance(request.getAccountId(), newBalance);

        logger.info("Withdrawal successful: {}", transactionId);

        return new WithdrawResponse(
            transactionId,
            request.getAccountId(),
            request.getAmount(),
            newBalance.toString(),
            true,
            "Withdrawal successful"
        );
    }

    @Override
    public DepositResponse deposit(DepositRequest request) {
        logger.info("Processing deposit: {}, amount: {}", request.getAccountId(), request.getAmount());

        BigDecimal currentBalance = getAccountBalance(request.getAccountId());
        BigDecimal amount = new BigDecimal(request.getAmount());

        sleep(300);

        String transactionId = UUID.randomUUID().toString();
        BigDecimal newBalance = currentBalance.add(amount);
        updateAccountBalance(request.getAccountId(), newBalance);

        logger.info("Deposit successful: {}", transactionId);

        return new DepositResponse(
            transactionId,
            request.getAccountId(),
            request.getAmount(),
            newBalance.toString(),
            true,
            "Deposit successful"
        );
    }

    private BigDecimal getAccountBalance(String accountId) {
        sleep(100);
        return mockBalances.getOrDefault(accountId, new BigDecimal("1000.00"));
    }

    private void updateAccountBalance(String accountId, BigDecimal newBalance) {
        logger.info("Updated balance for {}: {}", accountId, newBalance);
        sleep(100);
    }

    private void sleep(long millis) {
        try {
            Thread.sleep(millis);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException(e);
        }
    }
}
