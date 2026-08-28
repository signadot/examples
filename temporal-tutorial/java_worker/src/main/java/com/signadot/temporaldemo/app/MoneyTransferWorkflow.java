package com.signadot.temporaldemo.app;

import io.temporal.workflow.WorkflowInterface;
import io.temporal.workflow.WorkflowMethod;

@WorkflowInterface
public interface MoneyTransferWorkflow {
    @WorkflowMethod
    String run(PaymentDetails paymentDetails);
}
