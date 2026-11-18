"""usage-api: records billable events and serves daily usage per customer from ClickHouse."""
import os

import clickhouse_connect
from flask import Flask, jsonify, request
from waitress import serve

# "analytics" in the baseline. In a sandbox, the name of that sandbox's branch.
DATABASE = os.environ["CLICKHOUSE_DATABASE"]

ch = clickhouse_connect.get_client(
    dsn=os.environ["CLICKHOUSE_URL"],
    username=os.environ["CLICKHOUSE_USER"],
    password=os.environ["CLICKHOUSE_PASSWORD"],
    database=DATABASE,
    autogenerate_session_id=False,  # lets waitress threads share the client
)
app = Flask(__name__)


@app.post("/events")
def record_events():
    rows = [[e["customer"], e.get("event", "api_call")] for e in request.get_json()]
    ch.insert("events", rows, column_names=["customer", "event"])
    return jsonify(database=DATABASE, inserted=len(rows))


@app.get("/usage/<customer>")
def usage(customer):
    result = ch.query(
        "SELECT day, sum(events) FROM daily_usage"
        " WHERE customer = {customer:String} AND day > today() - 7"
        " GROUP BY day ORDER BY day",
        parameters={"customer": customer},
    )
    days = [{"day": str(day), "events": events} for day, events in result.result_rows]
    return jsonify(database=DATABASE, customer=customer, days=days)


@app.get("/healthz")
def healthz():
    return "ok"


if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=8080)
