package com.signadot.temporaldemo.signadot;

import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import java.net.URL;
import java.util.HashSet;
import java.util.Set;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

public class RoutesClient {
    private static final Logger logger = LoggerFactory.getLogger(RoutesClient.class);

    private final String sandboxName;
    private final String routeServerAddr;
    private final String baselineKind;
    private final String baselineNamespace;
    private final String baselineName;
    private final int refreshIntervalSeconds;

    private final OkHttpClient httpClient = new OkHttpClient();
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final AtomicReference<Set<String>> routingKeysCache = new AtomicReference<>(new HashSet<>());
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
        try {
            return java.net.URLEncoder.encode(value, "UTF-8");
        } catch (java.io.UnsupportedEncodingException e) {
            return value;
        }
    }

    private void fetchAndUpdate() {
        String url = buildRoutesUrl();
        try {
            Request request = new Request.Builder()
                .url(url)
                .get()
                .build();

            try (Response response = httpClient.newCall(request).execute()) {
                if (!response.isSuccessful()) {
                    logger.error("RoutesClient: Error fetching routes. Status: {}, Body: {}",
                        response.code(), response.body() != null ? response.body().string() : "");
                    return;
                }

                String body = response.body() != null ? response.body().string() : "";
                JsonNode data = objectMapper.readTree(body);
                Set<String> newKeys = new HashSet<>();

                JsonNode routingRules = data.get("routingRules");
                if (routingRules != null && routingRules.isArray()) {
                    for (JsonNode rule : routingRules) {
                        JsonNode routingKey = rule.get("routingKey");
                        if (routingKey != null && !routingKey.isNull()) {
                            newKeys.add(routingKey.asText());
                        }
                    }
                }

                Set<String> oldKeys = routingKeysCache.get();
                if (!newKeys.equals(oldKeys)) {
                    logger.info("RoutesClient: Routing keys updated: {}", newKeys);
                }
                routingKeysCache.set(newKeys);
            }
        } catch (Exception e) {
            logger.error("RoutesClient: Error during route fetch: {}", e.getMessage(), e);
        }
    }

    public void startPolling() {
        String target = sandboxName.isEmpty() ? "baseline" : "sandbox '" + sandboxName + "'";
        logger.info("RoutesClient: Starting periodic cache updater for {} with {}s polling interval",
            target, refreshIntervalSeconds);

        // Perform initial fetch
        fetchAndUpdate();

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

    public boolean shouldProcess(String routingKey) {
        if (routingKey == null) {
            routingKey = "";
        }

        Set<String> currentCache = routingKeysCache.get();

        if (!sandboxName.isEmpty()) {
            boolean should = !routingKey.isEmpty() && currentCache.contains(routingKey);
            logger.debug("Sandbox worker: routing_key={}, cache={}, should_process={}",
                routingKey, currentCache, should);
            return should;
        } else {
            boolean should = routingKey.isEmpty() || !currentCache.contains(routingKey);
            logger.debug("Baseline worker: routing_key={}, cache={}, should_process={}",
                routingKey, currentCache, should);
            return should;
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
