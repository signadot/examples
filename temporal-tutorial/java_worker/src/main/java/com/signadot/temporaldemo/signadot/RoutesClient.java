package com.signadot.temporaldemo.signadot;

import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.HashSet;
import java.util.Set;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;
import java.util.concurrent.locks.ReentrantLock;

public class RoutesClient {
    private static final Logger logger = LoggerFactory.getLogger(RoutesClient.class);

    /**
     * Rate limit for cache refreshes triggered by lookups of unknown routing
     * keys, so a stream of foreign-keyed tasks cannot turn every task into a
     * routeserver round trip.
     */
    private static final long MISS_REFRESH_MIN_INTERVAL_MS = 1_000;

    private final String sandboxName;
    private final String routeServerAddr;
    private final String baselineKind;
    private final String baselineNamespace;
    private final String baselineName;
    private final int refreshIntervalSeconds;

    private final OkHttpClient httpClient = new OkHttpClient();
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final AtomicReference<Set<String>> routingKeysCache = new AtomicReference<>(new HashSet<>());
    private final AtomicLong lastFetchAtMs = new AtomicLong(0);
    private final ReentrantLock missRefreshLock = new ReentrantLock();
    private ScheduledExecutorService refreshExecutor;

    public RoutesClient(String sandboxName) {
        this.sandboxName = sandboxName == null ? "" : sandboxName;
        this.routeServerAddr = requireEnv("ROUTES_API_ROUTE_SERVER_ADDR");
        this.baselineKind = requireEnv("ROUTES_API_BASELINE_KIND");
        this.baselineNamespace = requireEnv("ROUTES_API_BASELINE_NAMESPACE");
        this.baselineName = requireEnv("ROUTES_API_BASELINE_NAME");
        this.refreshIntervalSeconds = Integer.parseInt(
            System.getenv().getOrDefault("ROUTES_API_REFRESH_INTERVAL_SECONDS", "5")
        );
    }

    private String buildRoutesUrl() {
        StringBuilder sb = new StringBuilder(routeServerAddr);
        if (!routeServerAddr.endsWith("/")) {
            sb.append("/");
        }
        sb.append("api/v1/workloads/routing-rules");
        sb.append("?baselineKind=").append(urlEncode(baselineKind));
        sb.append("&baselineNamespace=").append(urlEncode(baselineNamespace));
        sb.append("&baselineName=").append(urlEncode(baselineName));
        if (!sandboxName.isEmpty()) {
            sb.append("&destinationSandboxName=").append(urlEncode(sandboxName));
        }
        return sb.toString();
    }

    private String urlEncode(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8);
    }

    /**
     * Queries the routeserver and updates the cache. Returns true on success;
     * on failure the old cache is retained.
     */
    private boolean fetchAndUpdate() {
        String url = buildRoutesUrl();
        lastFetchAtMs.set(System.currentTimeMillis());
        try {
            Request request = new Request.Builder()
                .url(url)
                .get()
                .build();

            try (Response response = httpClient.newCall(request).execute()) {
                if (!response.isSuccessful()) {
                    logger.error("RoutesClient: Error fetching routes. Status: {}, Body: {}",
                        response.code(), response.body() != null ? response.body().string() : "");
                    return false;
                }

                String body = response.body() != null ? response.body().string() : "";
                JsonNode data = objectMapper.readTree(body);
                Set<String> newKeys = new HashSet<>();

                JsonNode routingRules = data.get("routingRules");
                if (routingRules != null && routingRules.isArray()) {
                    for (JsonNode rule : routingRules) {
                        JsonNode routingKey = rule.get("routingKey");
                        if (routingKey != null && !routingKey.isNull() && !routingKey.asText().isEmpty()) {
                            newKeys.add(routingKey.asText());
                        }
                    }
                }

                Set<String> oldKeys = routingKeysCache.get();
                if (!newKeys.equals(oldKeys)) {
                    logger.info("RoutesClient: Routing keys updated: {}", newKeys);
                }
                routingKeysCache.set(newKeys);
                return true;
            }
        } catch (Exception e) {
            logger.error("RoutesClient: Error during route fetch: {}", e.getMessage(), e);
            return false;
        }
    }

    /**
     * Starts the periodic cache refresh. The initial fetch is synchronous and
     * fatal on error: starting a worker with an empty cache would let a
     * baseline worker accept sandbox-routed tasks (an isolation violation),
     * so we fail fast and let the orchestrator restart the pod. Same behavior
     * as the Go and TypeScript workers.
     */
    public void startPolling() {
        String target = sandboxName.isEmpty() ? "baseline" : "sandbox '" + sandboxName + "'";
        logger.info("RoutesClient: Starting periodic cache updater for {} with {}s polling interval",
            target, refreshIntervalSeconds);

        if (!fetchAndUpdate()) {
            throw new IllegalStateException(
                "RoutesClient: initial routes fetch failed; refusing to start with an empty routing cache");
        }

        // Start periodic refresh
        refreshExecutor = Executors.newScheduledThreadPool(1, r -> {
            Thread t = new Thread(r, "RoutesClient-Refresh");
            t.setDaemon(true);
            return t;
        });
        refreshExecutor.scheduleAtFixedRate(
            this::fetchAndUpdate,
            refreshIntervalSeconds,
            refreshIntervalSeconds,
            TimeUnit.SECONDS
        );
    }

    public void stopPolling() {
        if (refreshExecutor != null) {
            refreshExecutor.shutdown();
            try {
                if (!refreshExecutor.awaitTermination(5, TimeUnit.SECONDS)) {
                    refreshExecutor.shutdownNow();
                }
            } catch (InterruptedException e) {
                refreshExecutor.shutdownNow();
                Thread.currentThread().interrupt();
            }
        }
    }

    /**
     * Determines if a workflow/activity with the given routing key should be
     * processed by this worker. A miss on a non-empty key triggers a
     * rate-limited synchronous refresh so a sandbox worker can pick up a key
     * created between polls; refresh failures are tolerated and the decision
     * always falls back to the (possibly stale) cache. Callable from activity
     * code only — never from workflow code (it does I/O).
     */
    public boolean shouldProcess(String routingKey) {
        if (routingKey == null || routingKey.isEmpty()) {
            return sandboxName.isEmpty();
        }

        if (!routingKeysCache.get().contains(routingKey)) {
            refreshOnMiss();
        }

        Set<String> currentCache = routingKeysCache.get();
        boolean inCache = currentCache.contains(routingKey);
        boolean should = sandboxName.isEmpty() ? !inCache : inCache;
        logger.debug("{} worker: routing_key={}, cache={}, should_process={}",
            sandboxName.isEmpty() ? "Baseline" : "Sandbox", routingKey, currentCache, should);
        return should;
    }

    /**
     * Refreshes the cache at most once per MISS_REFRESH_MIN_INTERVAL_MS.
     * Concurrent callers don't wait for an in-flight refresh; they proceed
     * with the current cache.
     */
    private void refreshOnMiss() {
        if (!missRefreshLock.tryLock()) {
            return;
        }
        try {
            if (System.currentTimeMillis() - lastFetchAtMs.get() < MISS_REFRESH_MIN_INTERVAL_MS) {
                return;
            }
            fetchAndUpdate();
        } finally {
            missRefreshLock.unlock();
        }
    }

    private static String requireEnv(String name) {
        String value = System.getenv(name);
        if (value == null || value.isEmpty()) {
            throw new IllegalStateException("Missing required environment variable: " + name);
        }
        return value;
    }
}
