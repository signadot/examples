package main

import (
	"context"
	"log/slog"
	"os"

	"github.com/signadot/temporal-worker-go/app"
	"github.com/signadot/temporal-worker-go/signadot"
	"go.temporal.io/sdk/worker"
	"go.temporal.io/sdk/workflow"
)

func init() {
	// Configure structured logging
	handler := slog.NewTextHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelInfo,
	})
	slog.SetDefault(slog.New(handler))
}

func main() {
	ctx := context.Background()

	// Load configuration from environment
	cfg, err := signadot.LoadConfigFromEnv()
	if err != nil {
		slog.Error("Failed to load configuration", "err", err)
		os.Exit(1)
	}

	// Create sandbox-aware worker with application workflows and activities
	w, err := signadot.New(ctx, cfg, registerWorkflowsActivities)
	if err != nil {
		slog.Error("Failed to create worker", "err", err)
		os.Exit(1)
	}
	defer w.Stop()

	// Run the worker (blocks until interrupted)
	if err := w.Run(ctx); err != nil {
		slog.Error("Worker error", "err", err)
		os.Exit(1)
	}
}

// registerWorkflowsActivities registers the application workflows and activities
func registerWorkflowsActivities(r worker.Registry) error {
	// Register workflows
	moneyTransfer := &app.MoneyTransferWorkflow{}
	r.RegisterWorkflowWithOptions(moneyTransfer.Run, workflow.RegisterOptions{Name: "MoneyTransferWorkflow"})

	// Register activities
	activities := &app.BankingActivities{}
	r.RegisterActivity(activities.Withdraw)
	r.RegisterActivity(activities.Deposit)

	return nil
}
