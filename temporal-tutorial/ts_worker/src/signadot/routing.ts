/**
 * Client for fetching routing rules from the Signadot routeserver.
 * Node.js port of temporal_worker/routing.py: it maintains a periodically
 * refreshed cache of the routing keys that map to sandboxes of the baseline
 * workload, and answers "should this worker process this routing key?".
 */

const log = (msg: string) => console.log(`[RoutesAPIClient] ${msg}`);
const logError = (msg: string) => console.error(`[RoutesAPIClient] ${msg}`);

/**
 * Rate limit for cache refreshes triggered by lookups of unknown routing
 * keys, so a stream of foreign-keyed tasks cannot turn every task into a
 * routeserver round trip.
 */
const MISS_REFRESH_MIN_INTERVAL_MS = 1_000;

export class RoutesAPIClient {
  private readonly sandboxName: string;
  private readonly routeServerAddr: string;
  private readonly baselineKind: string;
  private readonly baselineNamespace: string;
  private readonly baselineName: string;
  private routingKeysCache: Set<string> = new Set();
  private refreshTimer?: NodeJS.Timeout;
  private refreshInFlight?: Promise<void>;
  private lastFetchAtMs = 0;

  constructor(sandboxName: string) {
    this.sandboxName = sandboxName;
    this.routeServerAddr = requireEnv('ROUTES_API_ROUTE_SERVER_ADDR');
    this.baselineKind = requireEnv('ROUTES_API_BASELINE_KIND');
    this.baselineNamespace = requireEnv('ROUTES_API_BASELINE_NAMESPACE');
    this.baselineName = requireEnv('ROUTES_API_BASELINE_NAME');
  }

  private buildRoutesUrl(): string {
    const url = new URL('/api/v1/workloads/routing-rules', this.routeServerAddr);
    url.searchParams.set('baselineKind', this.baselineKind);
    url.searchParams.set('baselineNamespace', this.baselineNamespace);
    url.searchParams.set('baselineName', this.baselineName);
    if (this.sandboxName) {
      url.searchParams.set('destinationSandboxName', this.sandboxName);
    }
    return url.toString();
  }

  private async fetchAndUpdate(): Promise<void> {
    const url = this.buildRoutesUrl();
    this.lastFetchAtMs = Date.now();
    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`Status: ${response.status}, Body: ${await response.text()}`);
      }
      const data = (await response.json()) as { routingRules?: Array<{ routingKey?: string }> };
      const newKeys = new Set<string>();
      for (const rule of data.routingRules ?? []) {
        if (rule?.routingKey != null) {
          newKeys.add(String(rule.routingKey));
        }
      }
      const changed =
        newKeys.size !== this.routingKeysCache.size || [...newKeys].some((k) => !this.routingKeysCache.has(k));
      if (changed) {
        log(`Routing keys updated: ${JSON.stringify([...newKeys])}`);
      }
      this.routingKeysCache = newKeys;
    } catch (err) {
      logError(`Error during route fetch: ${err}`);
      throw err;
    }
  }

  private refresh(): Promise<void> {
    if (this.refreshInFlight !== undefined) {
      return this.refreshInFlight;
    }
    const inFlight = this.fetchAndUpdate().finally(() => {
      this.refreshInFlight = undefined;
    });
    this.refreshInFlight = inFlight;
    return inFlight;
  }

  /**
   * Start the periodic cache refresh. The initial fetch is synchronous and
   * fatal on error: starting a worker with an empty cache would let a
   * baseline worker accept sandbox-routed tasks (an isolation violation),
   * so we fail fast and let the orchestrator restart the pod.
   */
  async startPolling(refreshIntervalSeconds: number): Promise<void> {
    const target = this.sandboxName ? `sandbox '${this.sandboxName}'` : 'baseline';
    log(`Starting periodic cache updater for ${target} with ${refreshIntervalSeconds}s polling interval`);
    await this.refresh();
    this.refreshTimer = setInterval(() => {
      void this.refresh().catch(() => undefined);
    }, refreshIntervalSeconds * 1000);
    this.refreshTimer.unref();
  }

  stopPolling(): void {
    if (this.refreshTimer) {
      clearInterval(this.refreshTimer);
      this.refreshTimer = undefined;
    }
  }

  /**
   * Determine if a workflow/activity with the given routing key should be
   * processed by this worker:
   * - Sandbox worker: only process routing keys that route to this sandbox.
   * - Baseline worker: process everything EXCEPT routing keys that route to
   *   some sandbox (unknown/stale keys fall back to baseline).
   *
   * An unknown non-empty key triggers a rate-limited refresh, so a sandbox
   * worker can pick up a key created between polls. Refresh failures are
   * tolerated: the decision always falls back to the (possibly stale) cache,
   * and a routeserver outage never turns into task failures.
   */
  async shouldProcess(routingKey: string): Promise<boolean> {
    if (routingKey === '') {
      return this.sandboxName === '';
    }
    if (
      !this.routingKeysCache.has(routingKey) &&
      Date.now() - this.lastFetchAtMs >= MISS_REFRESH_MIN_INTERVAL_MS
    ) {
      try {
        await this.refresh();
      } catch (err) {
        logError(`Refresh on cache miss failed; falling back to cached routing keys: ${err}`);
      }
    }
    if (this.sandboxName) {
      return this.routingKeysCache.has(routingKey);
    }
    return !this.routingKeysCache.has(routingKey);
  }
}

function requireEnv(name: string): string {
  const value = process.env[name];
  if (value === undefined || value === '') {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}
