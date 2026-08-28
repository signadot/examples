package app

import (
	"context"
	"fmt"
	"math/big"
	"time"

	"github.com/google/uuid"
	"go.temporal.io/sdk/activity"
)

// BankingActivities implements money transfer activities.
// Pure application logic; Signadot routing and OTel context propagation
// are handled entirely by the platform layer in the signadot package.
type BankingActivities struct{}

// Withdraw removes money from an account
func (a *BankingActivities) Withdraw(ctx context.Context, req WithdrawRequest) (*WithdrawResponse, error) {
	activity.GetLogger(ctx).Info("Processing withdrawal", "account_id", req.AccountID, "amount", req.Amount)

	balance := a.getAccountBalance(req.AccountID)

	// Parse amount and balance as big.Decimal equivalents
	reqAmount, ok := new(big.Float).SetString(req.Amount)
	if !ok {
		return nil, fmt.Errorf("invalid amount format: %s", req.Amount)
	}

	if balance.Cmp(reqAmount) < 0 {
		return nil, fmt.Errorf("insufficient funds: balance=%v, requested=%s", balance, req.Amount)
	}

	// Simulate processing
	time.Sleep(500 * time.Millisecond)

	txID := uuid.New().String()
	newBalance := new(big.Float).Sub(balance, reqAmount)

	activity.GetLogger(ctx).Info("Withdrawal successful", "transaction_id", txID)

	return &WithdrawResponse{
		TransactionID: txID,
		AccountID:     req.AccountID,
		Amount:        req.Amount,
		BalanceAfter:  newBalance.String(),
		Success:       true,
		Message:       "Withdrawal successful",
	}, nil
}

// Deposit adds money to an account
func (a *BankingActivities) Deposit(ctx context.Context, req DepositRequest) (*DepositResponse, error) {
	activity.GetLogger(ctx).Info("Processing deposit", "account_id", req.AccountID, "amount", req.Amount)

	balance := a.getAccountBalance(req.AccountID)

	// Parse amount as big.Decimal equivalent
	reqAmount, ok := new(big.Float).SetString(req.Amount)
	if !ok {
		return nil, fmt.Errorf("invalid amount format: %s", req.Amount)
	}

	// Simulate processing
	time.Sleep(300 * time.Millisecond)

	txID := uuid.New().String()
	newBalance := new(big.Float).Add(balance, reqAmount)

	activity.GetLogger(ctx).Info("Deposit successful", "transaction_id", txID)

	return &DepositResponse{
		TransactionID: txID,
		AccountID:     req.AccountID,
		Amount:        req.Amount,
		BalanceAfter:  newBalance.String(),
		Success:       true,
		Message:       "Deposit successful",
	}, nil
}

// getAccountBalance returns mock account balances
func (a *BankingActivities) getAccountBalance(accountID string) *big.Float {
	balances := map[string]string{
		"acc_001": "1000.00",
		"acc_002": "500.00",
		"acc_003": "2500.00",
		"acc_004": "750.00",
	}
	if balance, ok := balances[accountID]; ok {
		value, _ := new(big.Float).SetString(balance)
		return value
	}
	value, _ := new(big.Float).SetString("1000.00")
	return value
}
