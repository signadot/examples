package app

import (
	"time"

	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/workflow"
)

// MoneyTransferWorkflow implements a 2-step money transfer:
// withdraw from source account, then deposit to destination.
type MoneyTransferWorkflow struct{}

// Run executes the workflow
func (w *MoneyTransferWorkflow) Run(ctx workflow.Context, payment PaymentDetails) (string, error) {
	logger := workflow.GetLogger(ctx)
	logger.Info(
		"Starting money transfer",
		"from_account", payment.FromAccount,
		"to_account", payment.ToAccount,
		"amount", payment.Amount,
	)

	// Step 1: Withdraw
	withdrawReq := WithdrawRequest{
		AccountID: payment.FromAccount,
		Amount:    payment.Amount,
		Reference: payment.Reference,
	}

	opts := workflow.ActivityOptions{
		StartToCloseTimeout: 30 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			InitialInterval:    5 * time.Second,
			BackoffCoefficient: 2.0,
			MaximumInterval:    10 * time.Second,
			MaximumAttempts:    10,
		},
	}
	ctx = workflow.WithActivityOptions(ctx, opts)

	var withdrawResult WithdrawResponse
	if err := workflow.ExecuteActivity(ctx, "Withdraw", withdrawReq).Get(ctx, &withdrawResult); err != nil {
		return "", err
	}

	logger.Info("Withdrawal successful", "transaction_id", withdrawResult.TransactionID)

	// Step 2: Deposit
	depositReq := DepositRequest{
		AccountID: payment.ToAccount,
		Amount:    payment.Amount,
		Reference: payment.Reference,
	}

	var depositResult DepositResponse
	if err := workflow.ExecuteActivity(ctx, "Deposit", depositReq).Get(ctx, &depositResult); err != nil {
		return "", err
	}

	logger.Info("Deposit successful", "transaction_id", depositResult.TransactionID)
	logger.Info("Money transfer completed successfully")

	return "Transfer complete: " + withdrawResult.TransactionID + " -> " + depositResult.TransactionID, nil
}
