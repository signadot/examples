# Runs locally with `signadot smart-test run` or as a hosted Smart Test triggered
# by the boxoffice/storefront Deployment. Test traffic writes to the shared demo DB.
payload = {
    "showId": "show-1",
    "seats": ["B11", "B12"],
    "currency": "USD",
    "idempotencyKey": "smart-hold-v2",
}
res = http.post(
    url = "http://storefront.boxoffice.svc:8080/reservations",
    json_body = payload,
    capture = True,
    name = "createReservation",
)
ck = smart_test.check("reservation-created")
if res.status_code != 201:
    ck.error("expected HTTP 201, got {}", res.status_code)

body = res.json()
ck_fields = smart_test.check("reservation-contract")
if type(body) != "dict":
    ck_fields.error("expected a JSON object")
else:
    for field in ["reservationId", "status", "seats", "expiresAt", "quote", "idempotencyKey"]:
        if field not in body:
            ck_fields.error("missing {}", field)
    if body.get("status") != "held" or body.get("seats") != payload["seats"]:
        ck_fields.error("response does not describe the requested hold")
    if not body.get("reservationId") or not body.get("expiresAt"):
        ck_fields.error("reservation id and expiry must be nonempty")
    if body.get("idempotencyKey") != payload["idempotencyKey"]:
        ck_fields.error("idempotency key changed")

ck_quote = smart_test.check("quote-with-fees")
if type(body) != "dict" or body.get("quote") != {"currency": "USD", "subtotal": 7000, "fees": 350, "total": 7350}:
    ck_quote.error("expected a USD quote of 7000 + 350 fees = 7350")

retry = http.post(url = "http://storefront.boxoffice.svc:8080/reservations", json_body = payload, name = "retryReservation")
ck_retry = smart_test.check("active-hold-idempotent")
if retry.status_code != 201 or retry.json() != body:
    ck_retry.error("retry changed the active reservation")

conflict = http.post(
    url = "http://storefront.boxoffice.svc:8080/reservations",
    json_body = {"showId": "show-1", "seats": ["B11", "B12"], "currency": "USD", "idempotencyKey": "smart-conflict-v2"},
    capture = True,
    name = "conflictingReservation",
)
ck_conflict = smart_test.check("held-seats-rejected")
if conflict.status_code != 409:
    ck_conflict.error("expected HTTP 409 for held seats, got {}", conflict.status_code)
