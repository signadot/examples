package com.signadot.temporaldemo.app;

import com.fasterxml.jackson.annotation.JsonProperty;

public class WithdrawResponse {
    @JsonProperty("transaction_id")
    private String transactionId;

    @JsonProperty("account_id")
    private String accountId;

    private String amount;

    @JsonProperty("balance_after")
    private String balanceAfter;

    private boolean success;

    private String message = "";

    public WithdrawResponse() {}

    public WithdrawResponse(String transactionId, String accountId, String amount, String balanceAfter, boolean success) {
        this.transactionId = transactionId;
        this.accountId = accountId;
        this.amount = amount;
        this.balanceAfter = balanceAfter;
        this.success = success;
    }

    public WithdrawResponse(String transactionId, String accountId, String amount, String balanceAfter, boolean success, String message) {
        this.transactionId = transactionId;
        this.accountId = accountId;
        this.amount = amount;
        this.balanceAfter = balanceAfter;
        this.success = success;
        this.message = message;
    }

    public String getTransactionId() {
        return transactionId;
    }

    public void setTransactionId(String transactionId) {
        this.transactionId = transactionId;
    }

    public String getAccountId() {
        return accountId;
    }

    public void setAccountId(String accountId) {
        this.accountId = accountId;
    }

    public String getAmount() {
        return amount;
    }

    public void setAmount(String amount) {
        this.amount = amount;
    }

    public String getBalanceAfter() {
        return balanceAfter;
    }

    public void setBalanceAfter(String balanceAfter) {
        this.balanceAfter = balanceAfter;
    }

    public boolean isSuccess() {
        return success;
    }

    public void setSuccess(boolean success) {
        this.success = success;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }

    @Override
    public String toString() {
        return "WithdrawResponse{" +
                "transactionId='" + transactionId + '\'' +
                ", accountId='" + accountId + '\'' +
                ", amount='" + amount + '\'' +
                ", balanceAfter='" + balanceAfter + '\'' +
                ", success=" + success +
                ", message='" + message + '\'' +
                '}';
    }
}
