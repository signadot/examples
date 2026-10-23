from flask import Flask, request

import platform_redis

from . import events
from .config import REDIS_URL, STREAM

# platform_redis.Redis is redis.Redis plus OpenTelemetry context on XADD.
redis_client = platform_redis.Redis.from_url(REDIS_URL, decode_responses=True)


def create_app():
    app = Flask(__name__, static_folder="static", static_url_path="")

    @app.get("/")
    def index():
        return app.send_static_file("index.html")

    @app.get("/healthz")
    def healthz():
        return "ok"

    @app.post("/api/publish")
    def publish():
        data = request.get_json(silent=True) or request.form
        message = {"id": data.get("messageID", ""), "body": data.get("messageBody", "")}
        events.record(f"Publishing message to Redis stream {STREAM}", message)
        entry_id = redis_client.xadd(STREAM, message, maxlen=10_000, approximate=True)
        return {"entryID": entry_id}

    @app.get("/api/events")
    def list_events():
        found, cursor = events.read(request.args.get("cursor", "0"))
        return {"events": found, "cursor": cursor}

    return app
