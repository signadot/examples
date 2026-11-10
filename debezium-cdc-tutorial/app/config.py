import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@postgres:5432/demo")
KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "kafka:9092")
NOTIFIER_URL = os.getenv("NOTIFIER_URL", "http://notifier:4001")

# Debezium names topics <topic.prefix>.<schema>.<table>.
ORDERS_TOPIC = "demo.public.orders"
CONSUMER_GROUP = "fulfillment"

PORTS = {"orders": 4000, "notifier": 4001}

# v1 keeps the item name as is; v2 uppercases it.
FULFILLMENT_VERSION = os.getenv("FULFILLMENT_VERSION", "v1")
