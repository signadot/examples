package com.signadot.temporaldemo.app;

import com.fasterxml.jackson.annotation.JsonProperty;

public class WithdrawRequest {
    @JsonProperty("account_id")
    private String accountId;

    private String amount;

    private String reference = "";

    public WithdrawRequest() {}

    public WithdrawRequest(String accountId, String amount) {
        this.accountId = accountId;
        this.amount = amount;
    }

    public WithdrawRequest(String accountId, String amount, String reference) {
        this.accountId = accountId;
        this.amount = amount;
        this.reference = reference;
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

    public String getReference() {
        return reference;
    }

    public void setReference(String reference) {
        this.reference = reference;
    }

    @Override
    public String toString() {
        return "WithdrawRequest{" +
                "accountId='" + accountId + '\'' +
                ", amount='" + amount + '\'' +
                ", reference='" + reference + '\'' +
                '}';
    }
}
