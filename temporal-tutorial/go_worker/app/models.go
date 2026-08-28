package app

// PaymentDetails holds workflow input
type PaymentDetails struct {
	FromAccount string `json:"from_account"`
	ToAccount   string `json:"to_account"`
	Amount      string `json:"amount"`
	Currency    string `json:"currency"`
	Reference   string `json:"reference"`
}

// WithdrawRequest for activity input
type WithdrawRequest struct {
	AccountID string `json:"account_id"`
	Amount    string `json:"amount"`
	Reference string `json:"reference"`
}

// WithdrawResponse for activity output
type WithdrawResponse struct {
	TransactionID string `json:"transaction_id"`
	AccountID     string `json:"account_id"`
	Amount        string `json:"amount"`
	BalanceAfter  string `json:"balance_after"`
	Success       bool   `json:"success"`
	Message       string `json:"message"`
}

// DepositRequest for activity input
type DepositRequest struct {
	AccountID string `json:"account_id"`
	Amount    string `json:"amount"`
	Reference string `json:"reference"`
}

// DepositResponse for activity output
type DepositResponse struct {
	TransactionID string `json:"transaction_id"`
	AccountID     string `json:"account_id"`
	Amount        string `json:"amount"`
	BalanceAfter  string `json:"balance_after"`
	Success       bool   `json:"success"`
	Message       string `json:"message"`
}
