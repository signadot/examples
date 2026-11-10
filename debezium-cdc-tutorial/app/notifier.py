from flask import Flask, request

from . import events


def create_app():
    app = Flask(__name__)

    @app.get("/healthz")
    def healthz():
        return "ok"

    @app.post("/api/notify")
    def notify():
        notification = request.get_json()
        events.record(notification["id"], f"Sent notification: \"{notification['text']}\"")
        return {}

    return app
