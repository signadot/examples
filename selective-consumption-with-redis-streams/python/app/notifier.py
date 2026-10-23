from flask import Flask, request

from . import events


def create_app():
    app = Flask(__name__)

    @app.get("/healthz")
    def healthz():
        return "ok"

    @app.post("/api/notify")
    def notify():
        message = request.get_json()
        events.record(f"Sent notification: \"{message['body']}\"", message)
        return {}

    return app
