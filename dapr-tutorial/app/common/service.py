"""Shared liveness, dependency readiness and human-readable API failures."""
import asyncio
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from signadot.routes_api import Workload
from signadot.routing import RoutingError, routing_headers

log = logging.getLogger(__name__)


def request_context(request):
    try:
        return routing_headers(request.headers)
    except RoutingError as exc:
        raise HTTPException(400, str(exc)) from exc


def install_errors(app):
    @app.exception_handler(RoutingError)
    async def routing_failure(_, exc):
        return JSONResponse(status_code=503, content={"error": "routing-unavailable", "detail": str(exc)})

    @app.exception_handler(httpx.HTTPError)
    async def downstream_failure(_, exc):
        detail = str(exc)
        if isinstance(exc, httpx.HTTPStatusError):
            detail = f"HTTP {exc.response.status_code}: {exc.response.text[:1000]}"
        return JSONResponse(status_code=502, content={"error": "downstream-failure", "detail": detail})


async def close_clients(*clients):
    await asyncio.gather(*(client.close() for client in clients if hasattr(client, "close")))


def client_lifespan(*clients):
    @asynccontextmanager
    async def lifespan(_):
        try:
            yield
        finally:
            await close_clients(*clients)
    return lifespan


def add_diagnostics(app, settings, routes, dapr, *, cache=None, store=None):
    @app.get("/healthz")
    async def health():
        return {"ok": True, **settings.identity}

    async def snapshot(name, refresh):
        if cache is not None and name == settings.baseline_name:
            # A RouteCache is actively polled, so staleness here means the poller is not
            # keeping up -- a real degradation.
            return {**cache.state(), "polled": True}
        workload = Workload("Deployment", settings.namespace, name)
        if not refresh:
            return routes.cached_state(workload, settings.routes_max_age)
        try:
            result = await routes.snapshot(workload, refresh_seconds=settings.routes_refresh,
                                           max_age=settings.routes_max_age)
            result.require_fresh(settings.routes_max_age)
            return {"loaded": True, "usable": True, "owners": result.owners,
                    "knownKeys": len(result.known_keys)}
        except (RoutingError, httpx.HTTPError) as exc:
            return {"loaded": False, "usable": False, "owners": {}, "knownKeys": 0,
                    "lastError": str(exc)}

    routing_state = {}

    async def diagnose(include_records=False, refresh_routes=True):
        result = {**settings.identity, "routes": {}, "errors": []}
        app_ids = None
        try:
            app_ids = settings.app_ids
            # Every Pod, baseline or fork, must run under the app ID the naming rule
            # gives it. A fork that does not is unreachable: callers compute the rule's
            # answer and invoke that.
            expected = app_ids.target(settings.workload, settings.sandbox or None)
            if expected != settings.app_id:
                raise RoutingError(f"Pod app ID {settings.app_id!r} disagrees with the naming rule, "
                                   f"which expects {expected!r}")
        except RoutingError as exc:
            result["errors"].append(str(exc))
        names = settings.routed_workloads
        states = await asyncio.gather(*(snapshot(name, refresh_routes) for name in names))
        result["routes"] = dict(zip(names, states))
        if app_ids is not None:
            for name, state in result["routes"].items():
                workload = Workload("Deployment", settings.namespace, name)
                try:
                    # Report the app ID each owning sandbox resolves to, so a reader can
                    # see the whole decision: key -> sandbox -> app ID.
                    state["appIDs"] = {key: app_ids.target(workload, owner)
                                       for key, owner in state["owners"].items()}
                except RoutingError as exc:
                    state["usable"] = False
                    state["lastError"] = str(exc)
        try:
            await dapr.ready(settings.app_id)
            result["daprReady"] = True
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - a probe must never raise
            # Previously only (RoutingError, httpx.HTTPError, ValueError) were caught, so a
            # probe arriving during shutdown -- exactly when the kubelet is still scraping --
            # escaped as RuntimeError("Dapr client is closed"). httpx.InvalidURL escaped too.
            result["daprReady"] = False
            result["errors"].append(str(exc))
        if store is not None:
            try:
                await store.ping()
                result["redisReady"] = True
                if include_records:
                    result["storage"] = await store.state()
            except Exception as exc:
                result["redisReady"] = False
                result["errors"].append(f"Redis unavailable: {exc}")
        # Keep ordinary baseline endpoints available during a route-server outage.
        # Keyed operations still enforce route freshness before invoking or ACKing.
        # Deliberately: /readyz stays 200 here, because failing readiness would pull
        # this Pod out of its Service and break the unkeyed baseline traffic that is
        # still perfectly serviceable. Routing failure is surfaced two other ways
        # instead -- an ERROR log on transition, and /routingz below -- because
        # `routingReady` was previously the only signal and nothing consumed it.
        result["ready"] = not result["errors"]
        # A workload this Pod has never needed to resolve reports loaded=False with no
        # error. That is "not asked yet", not "broken" -- a subscriber never invokes the
        # checkout workload, and a publisher never resolves anything. Counting those as
        # failures made /routingz a permanent false alarm on every role except a caller
        # that had just performed a keyed invoke. Only an actual failure counts: a
        # snapshot that loaded and went stale, or one that recorded an error.
        def failed(state):
            # An on-demand snapshot expires when nothing needs it: the frontend loads
            # checkout's rules during a keyed invoke and they age out while idle, then
            # refetch on the next keyed request. That is not a failure, and treating it as
            # one made /routingz flap to 503 within seconds of every successful run.
            # Only a recorded error, or an actively-polled cache going stale, is degradation.
            if state.get("lastError"):
                return True
            return bool(state.get("polled")) and state["loaded"] and not state["usable"]
        result["routingDegraded"] = sorted(n for n, s in result["routes"].items() if failed(s))
        result["routingReady"] = result["ready"] and not result["routingDegraded"]
        if result["routingReady"] != routing_state.get("last"):
            routing_state["last"] = result["routingReady"]
            if result["routingReady"]:
                log.info("routing ready: keyed requests can be resolved")
            else:
                detail = "; ".join(
                    f"{name}: {result['routes'][name].get('lastError') or 'snapshot loaded but stale'}"
                    for name in result["routingDegraded"]
                ) or "; ".join(result["errors"])
                log.error("routing NOT ready, keyed requests will fail: %s", detail)
        return result

    @app.get("/readyz")
    async def ready():
        result = await diagnose(refresh_routes=False)
        return JSONResponse(status_code=200 if result["ready"] else 503, content=result)

    @app.get("/routingz")
    async def routing_ready():
        """Routing-specific probe: 503 when keyed requests cannot be resolved.

        Deliberately separate from /readyz. Use this for alerting, never as a
        Kubernetes readinessProbe -- doing so would remove a Pod that is still
        serving baseline traffic correctly during a route-server outage.
        """
        result = await diagnose(refresh_routes=False)
        return JSONResponse(status_code=200 if result["routingReady"] else 503, content=result)

    @app.get("/state")
    @app.get("/routing")
    async def state():
        return await diagnose(include_records=True)


def passthrough(response):
    try:
        body = response.json()
    except ValueError:
        body = {"error": "downstream-non-json-response", "detail": response.text[:1000]}
    return JSONResponse(status_code=response.status_code, content=body)
