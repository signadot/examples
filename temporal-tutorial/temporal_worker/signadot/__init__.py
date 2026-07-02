"""
Signadot platform layer for Temporal workers.

This package contains everything needed to make a Temporal worker
sandbox-aware: routing-key based task selection, routeserver integration, and
OpenTelemetry context/baggage propagation. It is owned by the platform team.

Application developers only need `SandboxAwareWorker` (and, when calling other
services with an HTTP client that is not auto-instrumented,
`outbound_http_headers`). Workflows and activities themselves require no
Signadot- or OpenTelemetry-specific code.
"""
from .worker import SandboxAwareWorker
from .interceptors import outbound_http_headers

__all__ = ["SandboxAwareWorker", "outbound_http_headers"]
