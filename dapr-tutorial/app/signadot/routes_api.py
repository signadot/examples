"""Small, custom Routes API adapter for native Dapr IDs and event ownership.

Routing keys are opaque. The Routes API names the sandbox that owns a key, and
the naming rule in signadot.appid turns that sandbox into the fork's Dapr app ID.
A local snapshot TTL bounds reuse; it cannot prove Routes Server convergence.
"""
from collections.abc import Mapping
from dataclasses import dataclass, asdict
import asyncio
import hashlib
import json
import math
import re
import time

import httpx

from signadot.appid import fork_app_id, is_fork_app_id, valid_app_id
from signadot.routing import RoutingError, routing_key


@dataclass(frozen=True)
class Workload:
    kind: str
    namespace: str
    name: str

    @classmethod
    def parse(cls, value):
        if not isinstance(value, dict):
            raise RoutingError("baseline must be an object")
        values = [value.get(name) for name in ("kind", "namespace", "name")]
        if any(not isinstance(part, str) or not part.strip() for part in values):
            raise RoutingError("baseline requires kind, namespace and name")
        return cls(*values)


class AppIDs:
    """Baseline app IDs, plus the naming rule that gives every fork its own.

    Only the baselines are configuration, and they change when a service is renamed,
    not when someone opens a pull request. A fork's app ID is computed from the
    sandbox name the Routes API reports (see signadot.appid), so a sandbox created
    after this process started is reachable without any change here.
    """

    def __init__(self, baselines: Mapping[Workload, str]):
        if not isinstance(baselines, Mapping) or not baselines:
            raise RoutingError("AppIDs requires at least one baseline workload")
        self.baselines = {}
        identities = set()
        for workload, app_id in baselines.items():
            if not isinstance(workload, Workload):
                raise RoutingError("AppIDs keys must be Workload values")
            app_id = self.validate_id(app_id)
            if is_fork_app_id(app_id):
                raise RoutingError(f"baseline app ID {app_id!r} uses the prefix reserved for sandbox forks")
            identity = (workload.namespace, app_id)
            if identity in identities:
                raise RoutingError("app ID reused by independent workloads in one namespace")
            identities.add(identity)
            self.baselines[workload] = app_id
        # Every invocation this client emits is /v1.0/invoke/<app-id>/method, with no
        # namespace qualifier, and Dapr resolves an unqualified app ID in the *caller's*
        # namespace (direct_messaging.go: `return targetAppID, d.namespace, nil`). The
        # uniqueness check above is namespace-scoped, so a mapping could otherwise
        # carry two workloads in different namespaces sharing one native app ID and look
        # correct while both calls landed in the caller's namespace. Refuse that shape at
        # construction instead of emitting a call that cannot express it. Cross-namespace
        # support would require `app-id.namespace` targets, which validate_id forbids.
        namespaces = {workload.namespace for workload in self.baselines}
        if len(namespaces) > 1:
            raise RoutingError(
                "native invocation is single-namespace: the baselines are in "
                + ", ".join(sorted(namespaces))
                + ", but an unqualified Dapr app ID always resolves in the caller's namespace")

    @staticmethod
    def validate_id(value):
        if not valid_app_id(value):
            raise RoutingError("native app ID must be a DNS label of at most 58 characters (plus -dapr)")
        return value

    def target(self, workload, sandbox=None):
        """The app ID to invoke: the baseline's, or the named sandbox's fork."""
        if workload not in self.baselines:
            raise RoutingError("destination workload has no baseline app ID configured")
        if sandbox is None:
            return self.baselines[workload]
        try:
            return fork_app_id(sandbox, workload.kind, workload.namespace, workload.name)
        except ValueError as exc:
            raise RoutingError(f"cannot name the fork's app ID: {exc}") from exc


def unique_json_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RoutingError("duplicate JSON object field")
        result[key] = value
    return result


@dataclass(frozen=True)
class Rules:
    """Routing rules for one workload, plus every key the whole map carried.

    `owners` maps a routing key to the sandbox that forks *this* workload.
    `known_keys` holds every valid key in the document, for any workload. The
    pair is what lets a caller separate two cases that both look like "no owner":
    a key that is real but does not fork this workload (baseline is correct),
    and a key the map never carried at all (baseline would be a guess).
    """

    owners: dict[str, str]
    known_keys: frozenset[str]

    def owner_for(self, key):
        """Sandbox owning `key` for this workload, "" for baseline, else raise.

        Raising on an unknown key is deliberate. A silently incomplete map --
        observed from Routes API v1.3.2, whose server-side filters can drop
        rules that exist -- would otherwise be indistinguishable from a sandbox
        that simply does not fork this workload, and the caller would serve
        baseline while reporting success.
        """
        if key is None:
            return ""
        owner = self.owners.get(key)
        if owner is not None:
            return owner
        if key in self.known_keys:
            return ""
        raise RoutingError(
            "routing key is absent from the Routes API map; refusing to assume baseline")


def parse_rules(document, workload):
    if not isinstance(document, dict) or set(document) - {"routingRules"}:
        raise RoutingError("unexpected Routes API response object")
    rules = document.get("routingRules")
    if rules is None:
        return Rules({}, frozenset())
    if not isinstance(rules, list):
        raise RoutingError("routingRules must be an array")
    owners = {}
    known = set()
    destinations = {}
    for rule in rules:
        if not isinstance(rule, dict):
            raise RoutingError("Routes API returned a malformed workload")
        actual = Workload.parse(rule.get("baseline"))
        key = rule.get("routingKey")
        if not isinstance(key, str) or not key or len(key) > 4096 or re.search(r"[\s;,\x00-\x1f\x7f]", key):
            raise RoutingError("routing rule requires a valid opaque routing key")
        destination = rule.get("destinationSandbox")
        owner = destination.get("name") if isinstance(destination, dict) else None
        if not isinstance(owner, str) or not owner.strip():
            raise RoutingError("routing rule requires destinationSandbox.name")
        mappings = rule.get("mappings")
        if mappings is None:
            mappings = []
        if not isinstance(mappings, list):
            raise RoutingError("invalid workload mappings")
        for mapping in mappings:
            if not isinstance(mapping, dict):
                raise RoutingError("Routes API returned a malformed workload mapping")
            if mapping.get("trafficManager") is not None:
                # Traffic Manager routes are a Signadot feature this adapter does not
                # implement. Reject them only for *this* workload. The fetch is
                # deliberately unfiltered, so rejecting them globally let any unrelated
                # team enabling Traffic Manager anywhere in the estate disable keyed
                # routing for every workload using this client, once the snapshot aged
                # out. Their routing key still counts as known: it is a real key that
                # simply routes somewhere this adapter does not handle, and treating it
                # as unknown would make an honest baseline look like a broken map.
                if actual == workload:
                    raise RoutingError("Traffic Manager routes are unsupported for this workload")
                continue
            port, targets = mapping.get("workloadPort"), mapping.get("destinations")
            if type(port) is not int or not 1 <= port <= 65535 or not isinstance(targets, list) or not targets:
                raise RoutingError("invalid workload port or destinations")
            for target in targets:
                if (not isinstance(target, dict) or not isinstance(target.get("host"), str)
                    or not target["host"].strip() or type(target.get("port")) is not int
                    or not 1 <= target["port"] <= 65535):
                    raise RoutingError("invalid workload destination")
        identity = (actual, key)
        if identity in destinations and destinations[identity] != owner:
            raise RoutingError("conflicting destinations for workload and routing key")
        destinations[identity] = owner
        # Validate every rule in the unfiltered document, then own only exact
        # workload matches. Every valid key seen anywhere counts as known, which
        # is what separates "this sandbox does not fork this workload" from
        # "the map never carried this key".
        known.add(key)
        if actual == workload:
            owners[key] = owner
    return Rules(owners, frozenset(known))


@dataclass(frozen=True)
class Snapshot:
    rules: Rules
    obtained_at: float

    @property
    def owners(self):
        return self.rules.owners

    @property
    def known_keys(self):
        return self.rules.known_keys

    def require_fresh(self, max_age, clock=time.monotonic):
        now = clock()
        if (not math.isfinite(max_age) or max_age <= 0 or not math.isfinite(self.obtained_at)
            or now < self.obtained_at or now >= self.obtained_at + max_age):
            raise RoutingError("Routes API snapshot is unavailable or stale")
        return self.obtained_at + max_age


@dataclass(frozen=True)
class Resolution:
    app_id: str
    destination_sandbox: str | None
    routing_key: str | None
    valid_until: float


class RoutesClient:
    def __init__(self, url="http://routeserver.signadot.svc:7778", timeout=3.0, *, client=None,
                 max_response_bytes=8_000_000):
        self.url, self.timeout = url.rstrip("/"), timeout
        # The whole document is required (see fetch), so this bound is the hard
        # ceiling on estate size for this client: roughly max_response_bytes/456
        # rules, measured against a real rule. Past it every keyed request fails
        # rather than degrading, so it is configurable and its headroom is
        # reported in cached_state() for operators to watch.
        if (not isinstance(max_response_bytes, int) or isinstance(max_response_bytes, bool)
                or max_response_bytes <= 0):
            # float("inf") and float("nan") both make `len(raw) > cap` never true,
            # silently disabling the bound; nan reads as a value rather than as "off".
            raise RoutingError("max_response_bytes must be a positive integer")
        self.max_response_bytes = max_response_bytes
        self.last_response_bytes = {}
        self._client, self._closed = client, False
        self._snapshots, self._errors, self._attempts, self._locks = {}, {}, {}, {}

    def client(self):
        if self._closed:
            raise RoutingError("Routes API client is closed")
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout, limits=httpx.Limits(
                max_connections=32, max_keepalive_connections=16))
        return self._client

    async def close(self):
        self._closed = True
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def fetch(self, workload):
        # Fetch unfiltered and filter locally. Routes API v1.3.2's `baselineName`
        # filter resolves through an index that is not namespace-qualified: when
        # two sandboxed baselines in different namespaces share a name, one owns
        # the slot and the others' rules become unreachable by name -- even when
        # `baselineNamespace` is supplied too. Measured: `baselineNamespace=ns`
        # returned that namespace's 4 rules, while `baselineNamespace=ns` plus
        # `baselineName=checkout` returned 0 of the 2 checkout rules inside them,
        # which AND-composed filters could never do. Over 10 polls a shadowed
        # workload's 2 rules were present unfiltered every time and returned by
        # name zero times. A dropped rule is indistinguishable from "no sandbox
        # forks this workload", so no server-side name filter may gate routing.
        # `baselineNamespace` measured correct and is namespace-unique, so it is
        # tempting for shrinking this payload. Do not use it: `known_keys` below
        # spans the WHOLE document, and that is what lets a real key belonging to
        # another namespace's sandbox resolve to baseline here instead of raising.
        # Scoping the fetch to one namespace would shrink `known_keys` with it and
        # turn every cross-namespace key into a spurious routing error -- the
        # normal case when a request enters namespace A with A's key and transits
        # to a service in namespace B. The completeness of this document is a
        # correctness requirement, not a performance choice.
        started = time.monotonic()
        try:
            async with self.client().stream("GET", self.url + "/api/v1/workloads/routing-rules",
                                            timeout=self.timeout) as response:
                response.raise_for_status()
                raw = bytearray()
                async for chunk in response.aiter_bytes():
                    raw.extend(chunk)
                    if len(raw) > self.max_response_bytes:
                        raise RoutingError(
                            f"Routes API response exceeds the {self.max_response_bytes} byte bound "
                            f"for this client. The whole document is required to tell 'this key "
                            f"forks nothing here' from 'the map never carried this key', so it "
                            f"cannot be filtered server-side. Raise max_response_bytes if the "
                            f"estate has grown, and expect keyed routing to fail entirely until "
                            f"it is raised.")
            document = json.loads(raw, object_pairs_hook=unique_json_fields)
            self.last_response_bytes[workload] = len(raw)
            return Snapshot(parse_rules(document, workload), started)
        except (httpx.HTTPError, ValueError) as exc:
            raise RoutingError(f"Routes API lookup failed: {exc}") from exc

    def cached_state(self, workload, max_age=15.0):
        snapshot = self._snapshots.get(workload)
        usable = False
        if snapshot is not None:
            try:
                snapshot.require_fresh(max_age)
                usable = True
            except RoutingError:
                pass
        return {"loaded": snapshot is not None, "usable": usable,
                "owners": snapshot.owners if snapshot else {},
                "knownKeys": len(snapshot.known_keys) if snapshot else 0,
                "responseBytes": self.last_response_bytes.get(workload),
                "maxResponseBytes": self.max_response_bytes,
                "ageSeconds": time.monotonic() - snapshot.obtained_at if snapshot else None,
                "maxAgeSeconds": max_age, "lastError": self._errors.get(workload)}

    async def snapshot(self, workload, *, refresh_seconds=2.0, max_age=15.0):
        """Coalesce refreshes; failure never extends a prior snapshot's deadline."""
        if self._closed:
            raise RoutingError("Routes API client is closed")
        if any(not math.isfinite(v) or v <= 0 for v in (refresh_seconds, max_age)):
            raise RoutingError("route timing values must be positive and finite")
        async with self._locks.setdefault(workload, asyncio.Lock()):
            now = time.monotonic()
            if now >= self._attempts.get(workload, float("-inf")) + min(refresh_seconds, max_age):
                try:
                    result = await self.fetch(workload)
                    result.require_fresh(max_age)
                    self._snapshots[workload] = result
                    self._errors.pop(workload, None)
                except (RoutingError, httpx.HTTPError) as exc:
                    self._errors[workload] = str(exc)
                finally:
                    # Back off from completion, including slow failures. Using
                    # start time makes queued callers immediately fetch again
                    # when one lookup itself exceeds the refresh interval.
                    self._attempts[workload] = time.monotonic()
            snapshot = self._snapshots.get(workload)
            if snapshot is None:
                raise RoutingError(self._errors.get(workload, "Routes API snapshot has not loaded"))
            snapshot.require_fresh(max_age)
            return snapshot

    async def resolve(self, workload, headers, app_ids, max_age=15.0, refresh_seconds=2.0):
        if self._closed:
            raise RoutingError("Routes API client is closed")
        if any(not math.isfinite(v) or v <= 0 for v in (refresh_seconds, max_age)):
            raise RoutingError("route timing values must be positive and finite")
        key = routing_key(headers)
        if key is None:
            # No key has a deterministic baseline destination, resolved without
            # depending on route-server availability.
            return Resolution(app_ids.target(workload), None, None, time.monotonic() + max_age)
        snapshot = await self.snapshot(workload, refresh_seconds=refresh_seconds, max_age=max_age)
        valid_until = snapshot.require_fresh(max_age)
        # The map says which sandbox owns the key; the naming rule says which app ID
        # that sandbox's fork runs under. No lookup table sits between the two.
        sandbox = snapshot.rules.owner_for(key) or None
        return Resolution(app_ids.target(workload, sandbox), sandbox, key, valid_until)


class RouteCache:
    def __init__(self, workload, client, refresh_seconds=2.0, max_age=15.0, clock=time.monotonic):
        if any(not math.isfinite(value) or value <= 0 for value in (refresh_seconds, max_age)):
            raise ValueError("route timing values must be positive and finite")
        self.workload, self.client, self.clock = workload, client, clock
        self.refresh_seconds, self.max_age = refresh_seconds, max_age
        self.snapshot = None
        self.last_error = None

    async def refresh(self):
        try:
            self.snapshot = await self.client.fetch(self.workload)
            self.last_error = None
            return True
        except (RoutingError, httpx.HTTPError) as exc:
            self.last_error = str(exc)
            return False
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - see below
            # Anything else must not kill the poller. A RecursionError from deeply
            # nested JSON, or any unforeseen shape, previously escaped `run()` and
            # ended the task silently: the frozen snapshot kept reporting healthy
            # until it aged out, after which every keyed message failed with no
            # error recorded anywhere. Record it and keep polling.
            self.last_error = f"{type(exc).__name__}: {exc}"
            return False

    async def run(self):
        while True:
            try:
                await self.refresh()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - the poller must outlive one bad cycle
                self.last_error = f"{type(exc).__name__}: {exc}"
            await asyncio.sleep(self.refresh_seconds)

    def rules(self):
        if self.snapshot is None:
            raise RoutingError("Routes API snapshot has not loaded")
        self.snapshot.require_fresh(self.max_age, self.clock)
        return self.snapshot.rules

    def owners(self):
        return self.rules().owners

    def state(self):
        try:
            self.owners()
            usable = True
        except RoutingError:
            usable = False
        owners = self.snapshot.owners if self.snapshot else {}
        return {"loaded": self.snapshot is not None, "usable": usable,
                "knownKeys": len(self.snapshot.known_keys) if self.snapshot else 0,
                "ageSeconds": self.clock() - self.snapshot.obtained_at if self.snapshot else None,
                "maxAgeSeconds": self.max_age, "owners": owners,
                "version": hashlib.sha256(json.dumps(owners, sort_keys=True).encode()).hexdigest()[:16]
                if self.snapshot else None, "lastError": self.last_error,
                "baseline": asdict(self.workload)}
