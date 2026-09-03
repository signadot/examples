"""
Where the Signadot routing key lives, and how to carry it along.

Signadot identifies sandbox traffic by an opaque *routing key*. On HTTP requests
it travels in the W3C `baggage` header as `sd-routing-key=<key>` (and, as a
fallback, in the `tracestate` header). Anything that forwards a request, or
turns a request into a message, must carry it along so the next hop can route.

Docs: https://www.signadot.com/docs/guides/set-up-context-propagation
"""
from typing import Mapping, Optional

ROUTING_KEY = "sd-routing-key"

# Headers Signadot routes on (baggage, tracestate), plus traceparent because
# some libraries drop tracestate unless traceparent is present too.
ROUTING_HEADERS = ("baggage", "tracestate", "traceparent")


def routing_headers(headers: Mapping[str, str]) -> dict:
    """Return the subset of `headers` that carries routing context.

    A service attaches these to every outbound call it makes on behalf of an
    inbound request, so the routing key survives the hop.
    """
    return {name: headers[name] for name in ROUTING_HEADERS if name in headers}


def routing_key(headers: Mapping[str, Optional[str]]) -> Optional[str]:
    """Extract the routing key from `baggage` (preferred) or `tracestate`.

    Returns None for baseline traffic (no key present).
    """
    for name in ("baggage", "tracestate"):
        value = headers.get(name)
        if value:
            key = _list_member(value, ROUTING_KEY)
            if key:
                return key
    return None


def routing_key_from_event(event: Mapping, headers: Mapping[str, str]) -> Optional[str]:
    """Extract the routing key from a CloudEvent delivered by Dapr.

    `checkout` copies the inbound `baggage` header into the CloudEvent as an
    extension attribute of the same name, so the key rides inside the message
    regardless of the broker. Two fallbacks: Dapr copies the publisher's
    `tracestate` into the envelope when Dapr tracing is enabled, and the Kafka
    component delivers record headers as HTTP headers.
    """
    from_envelope = {"baggage": event.get("baggage"), "tracestate": event.get("tracestate")}
    return routing_key(from_envelope) or routing_key(headers)


def _list_member(header_value: str, name: str) -> Optional[str]:
    """Find `name=value` in a comma-separated list header (baggage, tracestate).

    Baggage members may carry `;property` suffixes, which are dropped.
    """
    for member in header_value.split(","):
        key, _, value = member.strip().partition("=")
        if key.strip() == name:
            return value.split(";", 1)[0].strip() or None
    return None
