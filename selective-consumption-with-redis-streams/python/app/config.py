import os

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
NOTIFIER_URL = os.getenv("NOTIFIER_URL", "http://notifier:4001")

STREAM = "demo:messages"
CONSUMER_GROUP = "demo-consumers"

PORTS = {"producer": 4000, "notifier": 4001}

# v1 keeps the message body as is; v2 uppercases it.
PROCESSOR_VERSION = os.getenv("PROCESSOR_VERSION", "v1")
