package com.signadot.temporaldemo.app;

import com.fasterxml.jackson.annotation.JsonProperty;

public class PaymentDetails {
    @JsonProperty("from_account")
    private String fromAccount;

    @JsonProperty("to_account")
    private String toAccount;

    private String amount;

    private String currency = "USD";

    private String reference = "";

    public PaymentDetails() {}

    public PaymentDetails(String fromAccount, String toAccount, String amount) {
        this.fromAccount = fromAccount;
        this.toAccount = toAccount;
        this.amount = amount;
    }

    public PaymentDetails(String fromAccount, String toAccount, String amount, String currency, String reference) {
        this.fromAccount = fromAccount;
        this.toAccount = toAccount;
        this.amount = amount;
        this.currency = currency;
        this.reference = reference;
    }

    public String getFromAccount() {
        return fromAccount;
    }

    public void setFromAccount(String fromAccount) {
        this.fromAccount = fromAccount;
    }

    public String getToAccount() {
        return toAccount;
    }

    public void setToAccount(String toAccount) {
        this.toAccount = toAccount;
    }

    public String getAmount() {
        return amount;
    }

    public void setAmount(String amount) {
        this.amount = amount;
    }

    public String getCurrency() {
        return currency;
    }

    public void setCurrency(String currency) {
        this.currency = currency;
    }

    public String getReference() {
        return reference;
    }

    public void setReference(String reference) {
        this.reference = reference;
    }

    @Override
    public String toString() {
        return "PaymentDetails{" +
                "fromAccount='" + fromAccount + '\'' +
                ", toAccount='" + toAccount + '\'' +
                ", amount='" + amount + '\'' +
                ", currency='" + currency + '\'' +
                ", reference='" + reference + '\'' +
                '}';
    }
}
