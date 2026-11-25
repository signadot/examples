"""Order console backend: resolve each workload, then invoke its native Dapr ID."""
import asyncio
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from common.config import Settings
from common.dapr import DaprClient
from common.models import OrderInput
from common.service import add_diagnostics, client_lifespan, install_errors, passthrough, request_context
from signadot.dapr import SignadotDaprClient
from signadot.routes_api import RoutesClient, Workload
from signadot.routing import RoutingError, routing_key


def create_app(settings=None, *, routes=None, dapr=None):
    settings = settings or Settings.from_env("frontend")
    routes, dapr = routes or RoutesClient(settings.routes_url), dapr or DaprClient(settings.dapr_url)
    integration = SignadotDaprClient(routes, dapr, settings.app_ids,
                                     max_age=settings.routes_max_age,
                                     refresh_seconds=settings.routes_refresh)
    app = FastAPI(title="Dapr + Signadot order console", lifespan=client_lifespan(routes, dapr))
    install_errors(app)
    add_diagnostics(app, settings, routes, dapr)

    @app.get("/api/contexts")
    async def contexts(request: Request):
        # A preview URL injects the routing key upstream of this Pod. Report it so
        # the console can follow the context it was actually opened in, instead of
        # offering a choice that the hosted endpoint would silently override.
        result = {"namespace": settings.namespace, "servedBy": settings.identity,
                  "requestRoutingKey": routing_key(request_context(request)),
                  "contexts": [routing_context(None, {})]}
        try:
            result["contexts"] += await sandbox_contexts()
        except RoutingError as exc:
            # Baseline needs no routing map, so the console stays usable without one.
            result["routesError"] = str(exc)
        return result

    def routing_context(key, sandboxes):
        """One selectable context: a routing key and the fork it selects per workload."""
        app_ids = settings.app_ids
        names = (settings.frontend_name, settings.checkout_name, settings.processor_name)
        owners = sorted(set(sandboxes.values()))
        return {"id": key or "baseline", "routingKey": key, "sandboxes": sandboxes,
                "label": "Baseline" if key is None else owners[0] if len(owners) == 1 else "Route group",
                "appIDs": {name: app_ids.target(Workload("Deployment", settings.namespace, name),
                                                sandboxes.get(name)) for name in names}}

    async def sandbox_contexts():
        """Every routing key that forks a workload in this namespace, from the Routes API.

        Nothing is configured per sandbox: one created by a pull request or an agent
        appears here as soon as the Routes API carries its key, and disappears with it.
        """
        names = (settings.frontend_name, settings.checkout_name, settings.processor_name)
        snapshots = await asyncio.gather(*(
            routes.snapshot(Workload("Deployment", settings.namespace, name),
                            refresh_seconds=settings.routes_refresh, max_age=settings.routes_max_age)
            for name in names))
        forks = {}
        for name, snapshot in zip(names, snapshots):
            for key, sandbox in snapshot.owners.items():
                forks.setdefault(key, {})[name] = sandbox
        found = [routing_context(key, sandboxes) for key, sandboxes in forks.items()]
        # Single sandboxes first, by name, then route groups.
        return sorted(found, key=lambda c: (c["label"] == "Route group", c["label"], c["id"]))

    async def invoke(name, path, request, *, verb="GET", order=None):
        response = await integration.invoke(Workload("Deployment", settings.namespace, name), path,
                                            headers=request_context(request), verb=verb, json=order)
        return passthrough(response)

    @app.post("/api/orders")
    async def place_order(order: OrderInput, request: Request):
        return await invoke(settings.checkout_name, "/orders", request, verb="POST", order=order.model_dump())

    @app.get("/api/processed")
    async def processed(request: Request):
        return await invoke(settings.processor_name, "/processed", request)

    static = Path(__file__).parent / "static"

    @app.get("/")
    async def index():
        return FileResponse(static / "index.html")

    app.mount("/static", StaticFiles(directory=static, check_dir=False), name="static")
    return app


app = create_app()
