-- The shared "analytics" database that the baseline usage-api reads and writes.
CREATE DATABASE IF NOT EXISTS analytics;

-- One row per billable event, partitioned by month.
CREATE TABLE IF NOT EXISTS analytics.events
(
    ts       DateTime DEFAULT now(),
    customer LowCardinality(String),
    event    LowCardinality(String)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(ts)
ORDER BY (customer, ts);

-- Daily totals per customer, which the API serves.
CREATE TABLE IF NOT EXISTS analytics.daily_usage
(
    day      Date,
    customer LowCardinality(String),
    events   UInt64
)
ENGINE = SummingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (customer, day);

-- Keeps daily_usage up to date on every insert into events.
CREATE MATERIALIZED VIEW IF NOT EXISTS analytics.daily_usage_mv TO analytics.daily_usage AS
SELECT toDate(ts) AS day, customer, count() AS events
FROM analytics.events
GROUP BY day, customer;

-- Seed: 300,000 events over the last 59 days, spread across three customers.
INSERT INTO analytics.events (ts, customer, event)
SELECT
    now() - toIntervalSecond(number * 17),
    ['acme', 'globex', 'initech'][number % 3 + 1],
    ['api_call', 'api_call', 'api_call', 'export'][number % 4 + 1]
FROM numbers(300000);
