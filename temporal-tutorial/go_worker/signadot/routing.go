package signadot

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"maps"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"
)

// missRefreshMinInterval rate-limits cache refreshes triggered by lookups of
// unknown routing keys, so a stream of foreign-keyed tasks cannot turn every
// task into a routeserver round trip.
const missRefreshMinInterval = time.Second

// RoutesAPIClient fetches and caches routing rules from the Signadot routeserver.
// Port of temporal_worker/routing.py: maintains a periodically refreshed cache
// of routing keys that map to sandboxes, answering "should this worker process this key?".
type RoutesAPIClient struct {
	sandboxName       string
	routeServerAddr   string
	baselineKind      string
	baselineNamespace string
	baselineName      string
	refreshInterval   time.Duration
	httpClient        *http.Client

	mu          sync.RWMutex
	routingKeys map[string]bool // set of routing keys we should process
	lastFetchAt time.Time       // last fetch attempt (success or failure)
	missMu      sync.Mutex      // serializes miss-triggered refreshes
	stopCh      chan struct{}
	stoppedCh   chan struct{}
}

// routingRulesResp is the shape of the routeserver response
type routingRulesResp struct {
	RoutingRules []struct {
		RoutingKey *string `json:"routingKey"`
	} `json:"routingRules"`
}

// NewRoutesAPIClient creates a client that queries the routeserver.
// Requires environment variables: ROUTES_API_ROUTE_SERVER_ADDR,
// ROUTES_API_BASELINE_KIND, ROUTES_API_BASELINE_NAMESPACE, ROUTES_API_BASELINE_NAME.
func NewRoutesAPIClient(sandboxName string, routeServerAddr, baselineKind, baselineNamespace, baselineName string) *RoutesAPIClient {
	// url.Parse treats "host:port" as scheme "host"; make scheme-less
	// addresses unambiguous up front.
	if !strings.Contains(routeServerAddr, "://") {
		routeServerAddr = "http://" + routeServerAddr
	}
	return &RoutesAPIClient{
		sandboxName:       sandboxName,
		routeServerAddr:   routeServerAddr,
		baselineKind:      baselineKind,
		baselineNamespace: baselineNamespace,
		baselineName:      baselineName,
		refreshInterval:   5 * time.Second,
		httpClient:        &http.Client{Timeout: 10 * time.Second},
		routingKeys:       make(map[string]bool),
		stopCh:            make(chan struct{}),
		stoppedCh:         make(chan struct{}),
	}
}

// SetRefreshInterval configures the polling interval
func (c *RoutesAPIClient) SetRefreshInterval(interval time.Duration) {
	c.refreshInterval = interval
}

// StartPolling begins the background refresh loop. The initial fetch is
// synchronous and fatal on error: starting a worker with an empty cache would
// let a baseline worker accept sandbox-routed tasks (an isolation violation),
// so we fail fast and let the orchestrator restart the pod.
func (c *RoutesAPIClient) StartPolling(ctx context.Context) error {
	if err := c.fetchAndUpdate(ctx); err != nil {
		slog.Error("Initial fetch failed", "err", err)
		return err
	}

	// Start background polling
	go c.pollLoop(ctx)
	return nil
}

// Stop halts the polling loop
func (c *RoutesAPIClient) Stop() {
	close(c.stopCh)
	<-c.stoppedCh
}

// ShouldProcess returns true if this worker should handle the routing key.
// Sandbox worker: only returns true for keys in the cache.
// Baseline worker: returns true for keys NOT in the cache (unknown/stale fall back).
//
// A miss on a non-empty key triggers a rate-limited synchronous refresh so a
// sandbox worker can pick up a key created between polls. Refresh failures are
// tolerated: the decision always falls back to the (possibly stale) cache.
// Callable from activity code only — never from workflow code (it does I/O).
func (c *RoutesAPIClient) ShouldProcess(routingKey string) bool {
	if routingKey == "" {
		return c.sandboxName == ""
	}

	if !c.hasKey(routingKey) {
		c.refreshOnMiss()
	}

	has := c.hasKey(routingKey)
	if c.sandboxName != "" {
		// Sandbox worker: only process keys routed to this sandbox
		return has
	}
	// Baseline worker: process everything except sandboxed keys
	return !has
}

func (c *RoutesAPIClient) hasKey(routingKey string) bool {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.routingKeys[routingKey]
}

// refreshOnMiss refreshes the cache at most once per missRefreshMinInterval.
// Concurrent callers don't wait for an in-flight refresh; they proceed with
// the current cache. Errors are logged inside fetchAndUpdate and swallowed.
func (c *RoutesAPIClient) refreshOnMiss() {
	if !c.missMu.TryLock() {
		return
	}
	defer c.missMu.Unlock()

	c.mu.RLock()
	recent := time.Since(c.lastFetchAt) < missRefreshMinInterval
	c.mu.RUnlock()
	if recent {
		return
	}

	_ = c.fetchAndUpdate(context.Background())
}

// pollLoop runs the periodic fetch (called in a goroutine)
func (c *RoutesAPIClient) pollLoop(ctx context.Context) {
	defer close(c.stoppedCh)
	ticker := time.NewTicker(c.refreshInterval)
	defer ticker.Stop()

	target := "baseline"
	if c.sandboxName != "" {
		target = fmt.Sprintf("sandbox '%s'", c.sandboxName)
	}
	slog.Info(
		"RoutesAPIClient: Starting periodic cache updater",
		"target", target,
		"interval_seconds", c.refreshInterval.Seconds(),
	)

	for {
		select {
		case <-c.stopCh:
			return
		case <-ticker.C:
			_ = c.fetchAndUpdate(ctx)
		}
	}
}

// fetchAndUpdate queries the routeserver and updates the cache.
// On failure, the old cache is retained.
func (c *RoutesAPIClient) fetchAndUpdate(ctx context.Context) error {
	u := c.buildRoutesURL()

	c.mu.Lock()
	c.lastFetchAt = time.Now()
	c.mu.Unlock()

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, u, nil)
	if err != nil {
		slog.Error("Failed to build request", "err", err)
		return err
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		slog.Error("RoutesAPIClient: HTTP error", "err", err)
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		slog.Error(
			"RoutesAPIClient: Error fetching routes",
			"status", resp.StatusCode,
			"body", string(body),
		)
		return fmt.Errorf("status %d", resp.StatusCode)
	}

	var respData routingRulesResp
	if err := json.NewDecoder(resp.Body).Decode(&respData); err != nil {
		slog.Error("RoutesAPIClient: Failed to decode response", "err", err)
		return err
	}

	newKeys := make(map[string]bool)
	for _, rule := range respData.RoutingRules {
		if rule.RoutingKey != nil && *rule.RoutingKey != "" {
			newKeys[*rule.RoutingKey] = true
		}
	}

	c.mu.Lock()
	defer c.mu.Unlock()

	// Only log if keys changed
	if !maps.Equal(c.routingKeys, newKeys) {
		keys := make([]string, 0, len(newKeys))
		for k := range newKeys {
			keys = append(keys, k)
		}
		slog.Info("RoutesAPIClient: Routing keys updated", "keys", keys)
	}

	c.routingKeys = newKeys
	return nil
}

// buildRoutesURL constructs the routeserver request URL
func (c *RoutesAPIClient) buildRoutesURL() string {
	u, _ := url.Parse(c.routeServerAddr)
	u.Path = "/api/v1/workloads/routing-rules"

	q := u.Query()
	q.Set("baselineKind", c.baselineKind)
	q.Set("baselineNamespace", c.baselineNamespace)
	q.Set("baselineName", c.baselineName)
	if c.sandboxName != "" {
		q.Set("destinationSandboxName", c.sandboxName)
	}
	u.RawQuery = q.Encode()

	return u.String()
}
