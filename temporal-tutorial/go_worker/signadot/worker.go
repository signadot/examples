package signadot

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"strconv"

	"go.temporal.io/sdk/activity"
	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/interceptor"
	"go.temporal.io/sdk/worker"
)

// WorkerConfig holds sandbox-aware worker configuration
type WorkerConfig struct {
	TaskQueue           string
	TemporalServerURL   string
	RouteServerAddr     string
	BaselineKind        string
	BaselineNamespace   string
	BaselineName        string
	RefreshIntervalSecs int
	SandboxName         string
}

// LoadConfigFromEnv reads configuration from environment variables
func LoadConfigFromEnv() (*WorkerConfig, error) {
	cfg := &WorkerConfig{
		TaskQueue:           os.Getenv("TASK_QUEUE"),
		TemporalServerURL:   os.Getenv("TEMPORAL_SERVER_URL"),
		RouteServerAddr:     os.Getenv("ROUTES_API_ROUTE_SERVER_ADDR"),
		BaselineKind:        os.Getenv("ROUTES_API_BASELINE_KIND"),
		BaselineNamespace:   os.Getenv("ROUTES_API_BASELINE_NAMESPACE"),
		BaselineName:        os.Getenv("ROUTES_API_BASELINE_NAME"),
		SandboxName:         os.Getenv("SIGNADOT_SANDBOX_NAME"),
		RefreshIntervalSecs: 5,
	}

	// Validate required fields
	if cfg.TaskQueue == "" {
		return nil, fmt.Errorf("missing required env var: TASK_QUEUE")
	}
	if cfg.TemporalServerURL == "" {
		return nil, fmt.Errorf("missing required env var: TEMPORAL_SERVER_URL")
	}
	if cfg.RouteServerAddr == "" {
		return nil, fmt.Errorf("missing required env var: ROUTES_API_ROUTE_SERVER_ADDR")
	}
	if cfg.BaselineKind == "" {
		return nil, fmt.Errorf("missing required env var: ROUTES_API_BASELINE_KIND")
	}
	if cfg.BaselineNamespace == "" {
		return nil, fmt.Errorf("missing required env var: ROUTES_API_BASELINE_NAMESPACE")
	}
	if cfg.BaselineName == "" {
		return nil, fmt.Errorf("missing required env var: ROUTES_API_BASELINE_NAME")
	}

	// Refresh interval is optional
	if s := os.Getenv("ROUTES_API_REFRESH_INTERVAL_SECONDS"); s != "" {
		if n, err := strconv.Atoi(s); err == nil {
			cfg.RefreshIntervalSecs = n
		}
	}

	return cfg, nil
}

// SandboxAwareWorker wraps the Temporal worker with Signadot routing and OTel support.
// Application code provides workflows and activities; the platform layer handles
// routing checks, cache management, and context propagation.
type SandboxAwareWorker struct {
	client       client.Client
	worker       worker.Worker
	routesClient *RoutesAPIClient
}

// New creates and starts a sandbox-aware worker
func New(ctx context.Context, cfg *WorkerConfig, registerFunc func(worker.Registry) error) (*SandboxAwareWorker, error) {
	// Create Temporal client
	tc, err := client.Dial(client.Options{
		HostPort: cfg.TemporalServerURL,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to connect to Temporal server: %w", err)
	}

	slog.Info(
		"Connected to Temporal server",
		"host", cfg.TemporalServerURL,
	)

	// Create routes client
	routesClient := NewRoutesAPIClient(
		cfg.SandboxName,
		cfg.RouteServerAddr,
		cfg.BaselineKind,
		cfg.BaselineNamespace,
		cfg.BaselineName,
	)

	// Start background polling
	if err := routesClient.StartPolling(ctx); err != nil {
		tc.Close()
		return nil, fmt.Errorf("failed to start routes polling: %w", err)
	}

	// Create the local activity that workflows use for routing checks
	shouldProcessFunc := func(ctx context.Context, routingKey string) (bool, error) {
		should := routesClient.ShouldProcess(routingKey)
		slog.Debug(
			"signadotShouldProcess",
			"routing_key", routingKey,
			"should_process", should,
		)
		return should, nil
	}

	// Create interceptor
	taskInterceptor := NewSelectiveTaskInterceptor(
		routesClient,
		cfg.SandboxName,
		cfg.TaskQueue,
		shouldProcessFunc,
	)

	// Create worker with interceptors
	w := worker.New(tc, cfg.TaskQueue, worker.Options{
		Identity: fmt.Sprintf("sandbox=%s task_queue=%s", cfg.SandboxName, cfg.TaskQueue),
		Interceptors: []interceptor.WorkerInterceptor{
			taskInterceptor,
		},
	})

	w.RegisterActivityWithOptions(shouldProcessFunc, activity.RegisterOptions{Name: "signadotShouldProcess"})

	// Register workflows and activities
	if err := registerFunc(w); err != nil {
		w.Stop()
		tc.Close()
		routesClient.Stop()
		return nil, fmt.Errorf("failed to register workflows/activities: %w", err)
	}

	slog.Info(
		"Worker created successfully",
		"sandbox", cfg.SandboxName,
		"task_queue", cfg.TaskQueue,
	)

	return &SandboxAwareWorker{
		client:       tc,
		worker:       w,
		routesClient: routesClient,
	}, nil
}

// Run starts polling for tasks (blocks until Stop is called)
func (w *SandboxAwareWorker) Run(ctx context.Context) error {
	slog.Info("Starting to poll for tasks...")
	return w.worker.Run(worker.InterruptCh())
}

// Stop halts the worker and closes connections
func (w *SandboxAwareWorker) Stop() {
	if w.worker != nil {
		w.worker.Stop()
	}
	if w.routesClient != nil {
		w.routesClient.Stop()
	}
	if w.client != nil {
		w.client.Close()
	}
}
