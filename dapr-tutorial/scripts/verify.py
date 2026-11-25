#!/usr/bin/env python3
"""Exercise the deployed tutorial and save observations as JSON.

This verifier creates demonstration orders and two schema-rejected test events.
It never installs software, changes
replica counts, replaces Pods, or changes the selected kubectl context. Every
kubectl invocation names the requested context and namespace explicitly.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import uuid


class VerificationError(RuntimeError):
    pass


def _load_naming_rule():
    """The adapter's own app-ID naming rule, loaded without its HTTP dependencies."""
    path = Path(__file__).resolve().parents[1] / "app" / "signadot" / "appid.py"
    spec = importlib.util.spec_from_file_location("appid", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.fork_app_id


fork_app_id = _load_naming_rule()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def request_json(url: str, *, key: str = "", data: dict | None = None,
                 timeout: float = 30) -> tuple[int, Any]:
    headers = {"accept": "application/json"}
    if key:
        headers["baggage"] = "sd-routing-key=" + key
    if data is not None:
        headers["content-type"] = "application/json"
    request = Request(url, headers=headers,
                      data=None if data is None else json.dumps(data).encode())
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw)
        except ValueError:
            body = {"non_json_error": raw[:2000]}
        return error.code, body


class Kubernetes:
    def __init__(self, context: str, namespace: str):
        self.prefix = ["kubectl", "--context", context, "--namespace", namespace]

    def run(self, *args: str, input: str | None = None, timeout: float = 30) -> str:
        result = subprocess.run(self.prefix + list(args), input=input, text=True,
                                capture_output=True, timeout=timeout, check=False)
        if result.returncode:
            raise VerificationError(f"kubectl {' '.join(args[:3])} failed: {result.stderr.strip()[:3000]}")
        return result.stdout

    def pods(self) -> list[dict]:
        return json.loads(self.run("get", "pods", "-o", "json"))["items"]

    @contextmanager
    def frontend(self, timeout: float):
        # Let kubectl choose the port atomically; reserving then releasing a
        # socket would introduce a race between concurrent verification runs.
        with tempfile.TemporaryFile(mode="w+t") as log:
            process = subprocess.Popen(
                self.prefix + ["port-forward", "--address=127.0.0.1", "service/frontend", ":8080"],
                stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                text=True,
            )
            try:
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    # Popen inherits the same open-file description. A seek on
                    # our reader would also move its writer's offset. pread
                    # leaves the child's append position untouched.
                    output = os.pread(log.fileno(), 65536, 0).decode("utf-8", errors="replace")
                    match = re.search(r"Forwarding from 127\.0\.0\.1:(\d+) ->", output)
                    if match:
                        yield f"http://127.0.0.1:{match.group(1)}"
                        return
                    if process.poll() is not None:
                        raise VerificationError(f"frontend port-forward exited: {output.strip()}")
                    time.sleep(.2)
                raise VerificationError("Timed out opening frontend port-forward")
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)


def scenarios_from_config(config: dict, namespace: str, name: str) -> list[dict]:
    """Find the tutorial's five contexts in the console's live list and compute expectations.

    The console lists every routing key the Routes API carries for this namespace, so
    other sandboxes may appear too; they are ignored here. Expected app IDs are computed
    independently from the naming rule, then compared with what the console reports.
    """
    require(config.get("namespace") == namespace, "Frontend configuration names the wrong namespace")
    workloads = {"frontend": "frontend", "checkout": "checkout", "processor": "order-processor"}
    sandboxes = {role: f"{name}-{role}" for role in workloads}
    baseline_ids = {workload: workload for workload in workloads.values()}
    fork_ids = {role: fork_app_id(sandboxes[role], "Deployment", namespace, workload)
                for role, workload in workloads.items()}
    wanted = {"baseline": {}, **{role: {workloads[role]: sandboxes[role]} for role in workloads},
              "combined": {workloads[role]: sandboxes[role] for role in workloads}}
    contexts = {}
    for entry in config.get("contexts", []):
        for context, forks in wanted.items():
            if entry.get("sandboxes") == forks:
                require(context not in contexts, f"More than one console context forks {forks or 'nothing'}")
                contexts[context] = entry
    ordered = ("baseline", "frontend", "checkout", "processor", "combined")
    require(set(contexts) == set(ordered),
            "Expected baseline, frontend, checkout, processor and combined contexts; found "
            + ", ".join(sorted(contexts)))
    keys = [contexts[role].get("routingKey") for role in ("frontend", "checkout", "processor", "combined")]
    require(all(isinstance(key, str) and bool(key) for key in keys) and len(set(keys)) == 4,
            "Sandbox and RouteGroup routing keys must be present and distinct")
    require(not contexts["baseline"].get("routingKey"), "Baseline context must have no routing key")
    result = []
    for context in ordered:
        console_fork = context in ("frontend", "combined")
        checkout_fork = context in ("checkout", "combined")
        processor_fork = context in ("processor", "combined")
        scenario = {
            "id": context, "routing_key": contexts[context].get("routingKey") or "",
            # The console fork is selected by Signadot's own routing, not by the
            # adapter, so it is asserted from the Pod that served the request.
            "console_app_id": fork_ids["frontend"] if console_fork else baseline_ids["frontend"],
            "checkout_app_id": fork_ids["checkout"] if checkout_fork else baseline_ids["checkout"],
            "processor_app_id": fork_ids["processor"] if processor_fork else baseline_ids["order-processor"],
            "checkout_sandbox": sandboxes["checkout"] if checkout_fork else "",
            "processor_sandbox": sandboxes["processor"] if processor_fork else "",
            "fulfillment": "priority" if processor_fork else "standard",
            "discount_percent": 10 if checkout_fork else 0,
        }
        reported = contexts[context].get("appIDs", {})
        require(reported == {"frontend": scenario["console_app_id"], "checkout": scenario["checkout_app_id"],
                             "order-processor": scenario["processor_app_id"]},
                f"{context}: the console's app IDs disagree with the naming rule: {reported}")
        result.append(scenario)
    return result


def check_checkout(body: dict, scenario: dict, order_id: str) -> int:
    require(body.get("order_id") == order_id, "Checkout did not preserve the submitted order ID")
    require(body.get("handled_by", {}).get("app_id") == scenario["checkout_app_id"],
            f"{scenario['id']}: wrong checkout app ID")
    require((body.get("routing_key") or "") == scenario["routing_key"],
            f"{scenario['id']}: checkout lost routing context")
    require(body.get("item") == "coffee" and body.get("quantity") == 2,
            f"{scenario['id']}: checkout changed order contents")
    total = body.get("total_cents")
    require(type(total) is int and total > 0, "Checkout total_cents must be a positive integer")
    return total


def schema_rejection_cases(scenarios: list[dict], run_id: str) -> list[dict]:
    """Keep envelope/context valid; only the selected owner rejects the schema."""
    by_id = {scenario["id"]: scenario for scenario in scenarios}
    source = "urn:signadot:dapr-tutorial:acceptance-publisher"
    cases = []
    for context in ("baseline", "combined"):
        scenario = by_id[context]
        order_id = run_id + "-schema-" + context
        event = {"specversion": "1.0", "id": order_id, "source": source,
                 "type": "order.created", "datacontenttype": "application/json",
                 "data": {"id": order_id, "created_by": source,
                          "routing_key": scenario["routing_key"] or None,
                          "item": "coffee", "quantity": 2, "total_cents": 1000}}
        if scenario["routing_key"]:
            event["baggage"] = "sd-routing-key=" + scenario["routing_key"]
        if context == "baseline":
            event["data"]["quantity"] = "incompatible-business-schema"
            incompatibility = "quantity is not an integer"
        else:
            event["type"] = "order.created.v2"
            incompatibility = "unsupported business event type"
        # poison=True means check_effects asserts *zero* records and never compares
        # contents; the item/quantity are carried anyway so the case stays complete.
        cases.append({**scenario, "item": "coffee", "quantity": 2,
                      "id": "schema-" + context, "order_id": order_id,
                      "event_source": source, "event": event, "poison": True,
                      "incompatibility": incompatibility})
    return cases


def logical_records(observations: list[dict], expected_app_ids: set[str]) -> dict[str, list[dict]]:
    """Collapse replicas sharing one Redis ledger, while checking their agreement."""
    grouped: dict[str, list[dict]] = {}
    for observation in observations:
        app_id = observation["app_id"]
        require(app_id in expected_app_ids, f"Unexpected processor app ID {app_id}")
        records = observation["orders"]
        require(isinstance(records, list), "Processor /processed response must contain an orders list")
        normalized = sorted(records, key=lambda record: json.dumps(record, sort_keys=True))
        if app_id in grouped:
            require(grouped[app_id] == normalized,
                    f"Replicas of {app_id} disagree about their shared processing ledger")
        grouped[app_id] = normalized
    require(set(grouped) == expected_app_ids, "Did not inspect both logical processor groups")
    return grouped


# The order this verifier places. `check_effects` compares a worker's record against
# whatever the *case* says was ordered, not against these literals -- so a caller that
# supplies its own order contents (observe_browser_orders.py does) is checked against
# what it actually ordered rather than against this fixture.
ORDER_FIXTURE = {"item": "coffee", "quantity": 2}


def ordered(case: dict) -> tuple[str, int]:
    """Item and quantity this case ordered. Required: guessing would defeat the check."""
    try:
        item, quantity = case["item"], case["quantity"]
    except KeyError as exc:
        raise VerificationError(
            f"{case.get('order_id', case.get('id'))}: case does not record what was ordered; "
            "supply 'item' and 'quantity' so the worker's record can be compared to it") from exc
    return item, quantity


def check_effects(groups: dict[str, list[dict]], cases: list[dict]) -> dict[str, dict]:
    results = {}
    for case in cases:
        owner = case["processor_app_id"]
        order_id = case["order_id"]
        for app_id, records in groups.items():
            matching = [record for record in records if record.get("id") == order_id]
            expected_count = 0 if case.get("poison") or app_id != owner else 1
            require(len(matching) == expected_count,
                    f"{case['id']} order {order_id}: {app_id} has {len(matching)} effects; expected {expected_count}")
            if not expected_count:
                continue
            record = matching[0]
            require(record.get("processed_by") == owner, f"{order_id}: wrong processor identity in ledger")
            require(record.get("created_by") == case["checkout_app_id"], f"{order_id}: wrong event producer")
            require(record.get("source") == case["checkout_app_id"], f"{order_id}: worker lost the CloudEvent source")
            require((record.get("routing_key") or "") == case["routing_key"], f"{order_id}: worker lost routing context")
            require(record.get("fulfillment") == case["fulfillment"], f"{order_id}: wrong fulfillment behavior")
            item, quantity = ordered(case)
            require(record.get("item") == item and record.get("quantity") == quantity,
                    f"{order_id}: worker changed order contents "
                    f"(ordered {quantity} x {item!r}, recorded "
                    f"{record.get('quantity')!r} x {record.get('item')!r})")
            require(record.get("total_cents") == case["total_cents"], f"{order_id}: worker changed the checkout total")
            results[order_id] = record
    return results


def poll(operation, *, timeout: float, label: str, interval: float = 1, on_retry=None) -> Any:
    deadline = time.monotonic() + timeout
    last_error = None
    attempts = 0
    while True:
        attempts += 1
        try:
            return operation()
        except (VerificationError, URLError, TimeoutError, ConnectionError) as error:
            last_error = error
            if on_retry is not None:
                on_retry(error, attempts)
        if time.monotonic() >= deadline:
            raise VerificationError(f"Timed out waiting for {label}: {last_error}") from last_error
        time.sleep(min(interval, max(0, deadline - time.monotonic())))


def pod_app_id(pod: dict) -> str:
    containers = pod.get("spec", {}).get("containers", [])
    for container in containers:
        for variable in container.get("env", []):
            if variable.get("name") == "DAPR_APP_ID" and variable.get("value"):
                return variable["value"]
    for container in containers:
        args = container.get("command", []) + container.get("args", [])
        for index, argument in enumerate(args):
            if argument == "--app-id" and index + 1 < len(args):
                return args[index + 1]
            if argument.startswith("--app-id="):
                return argument.split("=", 1)[1]
    return pod.get("metadata", {}).get("annotations", {}).get("dapr.io/app-id", "")


def running(pod: dict) -> bool:
    return (not pod.get("metadata", {}).get("deletionTimestamp")
            and pod.get("status", {}).get("phase") == "Running")


def pod_is_ready(pod: dict) -> bool:
    return any(condition.get("type") == "Ready" and condition.get("status") == "True"
               for condition in pod.get("status", {}).get("conditions", []))


def check_routes(state: dict, scenarios: list[dict], *, required_roles: tuple[str, ...]) -> None:
    for role in required_roles:
        snapshot = state.get("routes", {}).get(role, {})
        require(snapshot.get("usable") is True and snapshot.get("loaded") is True,
                f"{state.get('app_id')}: {role} routing snapshot is not usable")
        owners = snapshot.get("owners")
        require(isinstance(owners, dict), f"{role} routing snapshot has no owners map")
        for scenario in scenarios:
            key = scenario["routing_key"]
            if not key:
                continue
            expected = scenario["checkout_sandbox" if role == "checkout" else "processor_sandbox"]
            require((owners.get(key) or "") == expected,
                    f"{state.get('app_id')}: {scenario['id']} routing has not converged for {role}")
            if expected:
                app_id = scenario["checkout_app_id" if role == "checkout" else "processor_app_id"]
                require((snapshot.get("appIDs") or {}).get(key) == app_id,
                        f"{state.get('app_id')}: {scenario['id']} resolves {role} to the wrong app ID")


class Probe:
    def __init__(self, kubernetes: Kubernetes, base_url: str, scenarios: list[dict], timeout: float,
                 evidence: dict | None = None, checkpoint=None):
        self.kubernetes = kubernetes
        self.base_url = base_url
        self.scenarios = scenarios
        self.timeout = timeout
        self.evidence = evidence if evidence is not None else {}
        self.checkpoint = checkpoint
        self.worker_ids = {scenario["processor_app_id"] for scenario in scenarios}
        self.checkout_ids = {scenario["checkout_app_id"] for scenario in scenarios}

    def api(self, path: str, *, key: str = "", data: dict | None = None,
            expected_status: int = 200) -> dict:
        observation = {"observed_at": timestamp(), "path": path, "routing_key": key,
                       "request": data, "status": None}
        self.evidence["latest_http_observation"] = observation
        try:
            status, body = request_json(self.base_url + path, key=key, data=data)
        except (URLError, TimeoutError, ConnectionError) as error:
            observation.update(error=f"{type(error).__name__}: {error}", finished_at=timestamp(),
                               response_received=False)
            if self.checkpoint is not None:
                self.checkpoint()
            # A timed-out POST may already have published. Preserve the attempted
            # order ID and stop; never retry a publication automatically here.
            raise
        observation.update(status=status, body=body, response_received=True, finished_at=timestamp())
        require(status == expected_status, f"{path} returned HTTP {status}: {body}")
        require(isinstance(body, dict), f"{path} did not return a JSON object")
        return body

    def console_routing(self) -> list[dict]:
        """Ask, from inside the cluster, which console answers each keyed request.

        A loopback port-forward is not intercepted by the DevMesh sidecar, so the
        console fork cannot be reached that way; observed on route-sidecar v1.3.2,
        where a port-forwarded request never appears in the sidecar's request log
        while an in-cluster request to the same endpoint does. This probe
        therefore calls the console Service from another Pod, which is the hop a
        reader's browser takes through a hosted preview endpoint.
        """
        pods = self.kubernetes.pods()
        clients = [pod for pod in pods if running(pod) and pod_is_ready(pod)
                   and pod_app_id(pod) in self.worker_ids]
        require(bool(clients), "No ready worker Pod available as an in-cluster console client")
        cases = [{"id": s["id"], "key": s["routing_key"], "expected": s["console_app_id"]} for s in self.scenarios]
        script = '''import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError
cases = json.loads(CASES)
results = []
for case in cases:
    headers = {"baggage": "sd-routing-key=" + case["key"]} if case["key"] else {}
    entry = dict(case)
    try:
        with urlopen(Request("http://frontend:8080/api/contexts", headers=headers), timeout=10) as response:
            entry["status"] = response.status
            body = json.load(response)
        entry["served_by"] = (body.get("servedBy") or {}).get("app_id")
        entry["variant"] = (body.get("servedBy") or {}).get("variant")
        entry["observed_key"] = body.get("requestRoutingKey") or ""
    except HTTPError as error:
        entry["status"] = error.code
        entry["error"] = error.read().decode(errors="replace")[:1000]
    except Exception as error:
        entry["status"] = None
        entry["error"] = type(error).__name__ + ": " + str(error)
    results.append(entry)
print(json.dumps(results))
'''.replace("CASES", repr(json.dumps(cases)), 1)
        observation = {
            "observed_at": timestamp(), "client_pod": clients[0]["metadata"]["name"],
            "transport": "in-cluster request to service/frontend; a port-forward is not routed",
            "requested_cases": cases, "cases": None, "passed": False}
        self.evidence["console_routing"] = observation
        try:
            raw = self.kubernetes.run("exec", "-i", clients[0]["metadata"]["name"], "-c", "app", "--",
                                      "python", "-", input=script, timeout=max(30, len(cases) * 15))
            try:
                observed = json.loads(raw)
            except ValueError as error:
                observation["raw_output"] = raw[:4000]
                raise VerificationError("Console probe did not return valid JSON") from error
            observation["cases"] = observed
            require(isinstance(observed, list), "Console probe results must be a list")
            require(bool(cases) and len(observed) == len(cases),
                    f"Console probe returned {len(observed)} results for {len(cases)} configured scenarios")
            expected = {case["id"]: case for case in cases}
            seen = set()
            for entry in observed:
                require(isinstance(entry, dict), "Console probe result must be an object")
                case_id = entry.get("id")
                require(isinstance(case_id, str) and case_id in expected,
                        f"Console probe returned an unexpected scenario ID: {case_id!r}")
                require(case_id not in seen, f"Console probe returned duplicate scenario {case_id!r}")
                seen.add(case_id)
                case = expected[case_id]
                require(type(entry.get("status")) is int and entry["status"] == 200,
                        f"{case_id}: console request returned {entry.get('status')}: {str(entry.get('error'))[:200]}")
                require(entry.get("served_by") == case["expected"],
                        f"{case_id}: console served by {entry.get('served_by')!r}, expected {case['expected']!r}")
                require(entry.get("observed_key") == case["key"],
                        f"{case_id}: console observed routing key {entry.get('observed_key')!r}, expected {case['key']!r}")
                require(entry.get("expected") == case["expected"] and entry.get("key") == case["key"],
                        f"{case_id}: console probe changed its configured expectation")
            require(seen == set(expected), "Console probe did not cover every configured scenario")
            observation["passed"] = True
        except Exception as error:
            observation["error"] = f"{type(error).__name__}: {error}"
            raise
        finally:
            observation["finished_at"] = timestamp()
            if self.checkpoint is not None:
                self.checkpoint()
        return observed

    def observations(self, *, include_checkout: bool = False) -> list[dict]:
        pods = self.kubernetes.pods()
        self.evidence["latest_pod_inventory"] = {
            "observed_at": timestamp(), "namespace_pod_count": len(pods),
            "application_pods": [{"pod": pod["metadata"]["name"], "app_id": pod_app_id(pod),
                                  "phase": pod.get("status", {}).get("phase"), "ready": pod_is_ready(pod)}
                                 for pod in pods if pod_app_id(pod) in self.worker_ids | self.checkout_ids
                                 or pod.get("metadata", {}).get("labels", {}).get("app") == "frontend"],
        }
        frontends = [pod for pod in pods if running(pod) and pod_is_ready(pod)
                     and pod.get("metadata", {}).get("labels", {}).get("app") == "frontend"]
        require(bool(frontends), "No ready frontend Pod available for direct worker probes")
        app_ids = self.worker_ids | (self.checkout_ids if include_checkout else set())
        targets = []
        for pod in pods:
            app_id = pod_app_id(pod)
            if app_id not in app_ids or not running(pod):
                continue
            require(pod_is_ready(pod), f"Pod {pod['metadata']['name']} is not ready")
            ip = pod.get("status", {}).get("podIP")
            require(bool(ip), f"Pod {pod['metadata']['name']} has no IP")
            targets.append({"pod": pod["metadata"]["name"], "ip": ip, "app_id": app_id,
                            "worker": app_id in self.worker_ids})
        require({target["app_id"] for target in targets} == app_ids,
                "Not all configured app IDs have running Pods")
        # One exec reads every Pod IP. /processed?all=true bypasses only the
        # list filter; it neither invokes a handler nor changes routing/state.
        script = '''import json
from urllib.request import urlopen
from urllib.error import HTTPError
targets = json.loads(TARGETS)
results = []
for target in targets:
    result = dict(target)
    for field, path in [("ready", "/readyz"), ("state", "/state")] + ([("processed", "/processed?all=true")] if target["worker"] else []):
        address = "[" + target["ip"] + "]" if ":" in target["ip"] else target["ip"]
        try:
            with urlopen("http://" + address + ":8080" + path, timeout=8) as response:
                result[field] = {"status": response.status, "body": json.load(response)}
        except HTTPError as error:
            result[field] = {"status": error.code, "body": error.read().decode()[:2000]}
        except Exception as error:
            result[field] = {"status": None, "error": type(error).__name__ + ": " + str(error)}
    results.append(result)
print(json.dumps(results))
'''.replace("TARGETS", repr(json.dumps(targets)), 1)
        raw = self.kubernetes.run("exec", "-i", frontends[0]["metadata"]["name"],
                                  "-c", "app", "--", "python", "-", input=script,
                                  timeout=max(30, len(targets) * 25))
        observations = json.loads(raw)
        # Keep the observation that caused a failed assertion. Successful phase
        # snapshots below remain separate, so this cannot turn failure into pass.
        self.evidence["latest_pod_observations"] = {"observed_at": timestamp(), "pods": observations}
        for observation in observations:
            for field in ("ready", "state") + (("processed",) if observation["worker"] else ()):
                require(observation[field]["status"] == 200,
                        f"{observation['pod']} {field} returned {observation[field]['status']}")
                require(isinstance(observation[field].get("body"), dict),
                        f"{observation['pod']} {field} did not return a JSON object")
            require(observation["state"]["body"].get("app_id") == observation["app_id"],
                    f"{observation['pod']} reports a different app ID than its Pod configuration")
            if observation["worker"]:
                processed = observation["processed"]["body"]
                require(processed.get("app_id") == observation["app_id"],
                        f"{observation['pod']} returned another app's processing ledger")
                observation["orders"] = processed.get("orders")
        return observations

    def ready(self) -> dict:
        readiness = self.api("/readyz")
        require(readiness.get("ready") is True, "Frontend application is not ready")
        # Readiness no longer fetches routes: this explicit diagnostic establishes
        # convergence even when an otherwise healthy frontend has been idle.
        frontend = self.api("/state")
        check_routes(frontend, self.scenarios, required_roles=("checkout", "order-processor"))
        observations = self.observations(include_checkout=True)
        for observation in observations:
            role = "order-processor" if observation["worker"] else "checkout"
            require(observation["ready"]["body"].get("ready") is True, "Application Pod is not ready")
            check_routes(observation["state"]["body"], self.scenarios, required_roles=(role,))
        return {"frontend": frontend, "frontend_readiness": readiness, "pods": observations}

    def effects(self, cases: list[dict]) -> dict:
        observations = self.observations()
        groups = logical_records(observations, self.worker_ids)
        records = check_effects(groups, cases)
        return {"pods": observations, "logical_group_record_counts": {key: len(value) for key, value in groups.items()},
                "verified_records": records}

    def publish_schema_event(self, case: dict) -> dict:
        """One local Dapr POST, bypassing checkout's business input validation."""
        frontends = [pod for pod in self.kubernetes.pods() if running(pod) and pod_is_ready(pod)
                     and pod.get("metadata", {}).get("labels", {}).get("app") == "frontend"]
        require(bool(frontends), "No ready frontend Pod available for the test publisher")
        pod = sorted(frontends, key=lambda item: item["metadata"]["name"])[0]
        # These are the same tutorial component/topic names used by broker_settled.
        url = "http://127.0.0.1:3500/v1.0/publish/pubsub/orders"
        observation = {"started_at": timestamp(), "event": case["event"],
                       "event_source": case["event_source"], "event_id": case["order_id"],
                       "publisher_pod": pod["metadata"]["name"], "publisher_container": "app",
                       "publisher_app_id": pod_app_id(pod), "routing_key": case["routing_key"],
                       "destination": {"url": url, "pubsub": "pubsub", "topic": "orders",
                                       "selected_worker_app_id": case["processor_app_id"]},
                       "status": None, "response_received": False}
        self.evidence.setdefault("schema_rejection_publications", []).append(observation)
        # Persist stable source/ID and full intent before kubectl can publish.
        if self.checkpoint is not None:
            self.checkpoint()
        payload = json.dumps({"event": case["event"], "url": url})
        script = "payload = " + repr(payload) + "\n" + '''import json, os
from urllib.request import Request, urlopen
from urllib.error import HTTPError
parameters = json.loads(payload)
event = parameters["event"]
headers = {"content-type": "application/cloudevents+json"}
if event.get("baggage"):
    headers["baggage"] = event["baggage"]
if os.environ.get("DAPR_API_TOKEN"):
    headers["dapr-api-token"] = os.environ["DAPR_API_TOKEN"]
request = Request(parameters["url"], data=json.dumps(event).encode(), headers=headers, method="POST")
try:
    with urlopen(request, timeout=15) as response:
        result = {"status": response.status, "body": response.read().decode()[:2000], "response_received": True}
except HTTPError as error:
    result = {"status": error.code, "body": error.read().decode(errors="replace")[:2000], "response_received": True}
except Exception as error:
    result = {"status": None, "error": type(error).__name__ + ": " + str(error), "response_received": False}
print(json.dumps(result))
'''
        try:
            raw = self.kubernetes.run("exec", "-i", pod["metadata"]["name"], "-c", "app", "--",
                                      "python", "-", input=script, timeout=30)
            result = json.loads(raw)
            require(isinstance(result, dict), "Test publisher did not return an observation object")
            observation.update(result)
            require(result.get("response_received") is True and result.get("status") == 204,
                    f"Test publisher did not confirm native Dapr publication: {result}")
        except Exception as error:
            # A failed exec/response can follow a successful POST. Never retry it.
            observation["error"] = f"{type(error).__name__}: {error}"
            raise
        finally:
            observation["finished_at"] = timestamp()
            if self.checkpoint is not None:
                self.checkpoint()
        return observation

    def schema_rejections(self, cases: list[dict]) -> dict:
        snapshot = {"effects": self.effects(cases), "dead_letters": self.dlq()}
        self.evidence["latest_schema_rejection_observation"] = snapshot
        try:
            for case in cases:
                check_dead_letter(snapshot["dead_letters"], case, expected_app_ids=self.worker_ids)
        except VerificationError:
            if self.checkpoint is not None:
                self.checkpoint()
            raise
        return snapshot

    def redis(self, *command: str) -> Any:
        pods = self.kubernetes.pods()
        redis = [pod for pod in pods if running(pod) and pod_is_ready(pod)
                 and pod.get("metadata", {}).get("labels", {}).get("app") == "redis"]
        require(len(redis) == 1, "Expected one ready Redis Pod")
        containers = redis[0]["spec"]["containers"]
        redis_container = next((container["name"] for container in containers
                                if "redis" in container.get("image", "")), "redis")
        raw = self.kubernetes.run("exec", redis[0]["metadata"]["name"], "-c", redis_container,
                                  "--", "redis-cli", "--json", *command)
        return json.loads(raw)

    def broker_settled(self) -> dict[str, dict]:
        groups = self.redis("XINFO", "GROUPS", "orders")
        return check_broker_settled(groups, self.worker_ids)

    def dlq(self) -> dict[str, Any]:
        result = {}
        for app_id in sorted(self.worker_ids):
            stream = "orders-dlq-" + app_id
            result[app_id] = {"stream": stream, "entries": self.redis("XRANGE", stream, "-", "+")}
        return result


def check_broker_settled(raw_groups: list, expected_app_ids: set[str]) -> dict[str, dict]:
    require(isinstance(raw_groups, list), "Redis XINFO GROUPS did not return a group list")
    groups = {}
    for raw in raw_groups:
        group = raw if isinstance(raw, dict) else dict(zip(raw[::2], raw[1::2]))
        if group.get("name") in expected_app_ids:
            groups[group["name"]] = group
    require(set(groups) == expected_app_ids, "Expected processor consumer groups are not all present")
    for name, group in groups.items():
        require(group.get("pending") == 0 and group.get("lag") == 0,
                f"Consumer group {name} has not acknowledged all published stream entries: {group}")
    return groups


def observed_attempts(effects: dict, case: dict) -> int:
    identity = json.dumps([case["checkout_app_id"], case["order_id"]], separators=(",", ":"))
    digest = hashlib.sha256(identity.encode()).hexdigest()
    counts = [pod["state"]["body"].get("storage", {}).get("attempts", {}).get(digest)
              for pod in effects["pods"] if pod["app_id"] == case["processor_app_id"]]
    require(bool(counts) and all(type(count) is int and count > 0 for count in counts),
            "Worker shared state did not expose delivery attempts for the event")
    require(len(set(counts)) == 1, "Worker replicas disagree about event delivery attempts")
    return counts[0]


def event_matches(value: Any, order_id: str, source: str) -> bool:
    """Find a preserved event inside Redis's stream field/value representation."""
    if isinstance(value, str):
        try:
            return event_matches(json.loads(value), order_id, source)
        except (ValueError, RecursionError):
            return False
    if isinstance(value, dict):
        if value.get("id") == order_id and value.get("source") == source:
            return True
        return any(event_matches(item, order_id, source) for item in value.values())
    if isinstance(value, list):
        return any(event_matches(item, order_id, source) for item in value)
    return False


def check_dead_letter(dlqs: dict[str, dict], case: dict, *, expected_app_ids: set[str] | None = None) -> dict:
    require(case["processor_app_id"] in dlqs, "Did not inspect the intended worker DLQ")
    if expected_app_ids is not None:
        require(set(dlqs) == expected_app_ids, "Did not inspect both logical worker DLQs")
    source = case.get("event_source", case["checkout_app_id"])
    matches = {}
    for app_id, stream in dlqs.items():
        entries = stream.get("entries") or []
        matching = [entry for entry in entries if event_matches(entry, case["order_id"], source)]
        require(bool(matching) == (app_id == case["processor_app_id"]),
                f"Rejected event {case['order_id']} {'missing from intended' if app_id == case['processor_app_id'] else 'present in wrong'} DLQ {stream['stream']}")
        if matching:
            matches[app_id] = matching
    return matches


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


class Progress:
    """Phase evidence survives interruption; only completed checks claim success."""
    def __init__(self, report: dict, output: Path):
        self.report, self.output = report, output

    def checkpoint(self):
        self.report["checkpoint_at"] = timestamp()
        write_report(self.output, self.report)

    def stage(self, label: str):
        self.report["phase"] = label
        self.report.pop("pending_poll", None)
        print(f"[verify] {label}", file=sys.stderr, flush=True)
        self.checkpoint()

    def complete(self, label: str):
        self.report["phase"] = label
        self.report.pop("pending_poll", None)
        print(f"[verify] Completed: {label}", file=sys.stderr, flush=True)
        self.checkpoint()

    def wait(self, operation, *, timeout: float, label: str, interval: float = 1):
        self.stage("Waiting for " + label)
        last_checkpoint = 0.0
        last_logged_error = None
        first = True
        def retry(error, attempts):
            nonlocal last_checkpoint, last_logged_error, first
            message = str(error)
            self.report["pending_poll"] = {"label": label, "attempts": attempts,
                                            "latest_error": message, "observed_at": timestamp()}
            now = time.monotonic()
            if first or now - last_checkpoint >= 30:
                if first or message != last_logged_error:
                    print(f"[verify] {label}: {message[:400]}", file=sys.stderr, flush=True)
                    last_logged_error = message
                self.checkpoint()
                last_checkpoint = now
                first = False
        return poll(operation, timeout=timeout, label=label, interval=interval, on_retry=retry)


def verify(args: argparse.Namespace, report: dict) -> None:
    kubernetes = Kubernetes(args.context, args.namespace)
    report["request_path"] = {
        "transport": "mixed",
        "http_matrix": "kubectl port-forward to service/frontend",
        "console_routing": "in-cluster worker Pod to service/frontend",
        "routing_context": "explicit baggage header supplied by verifier",
        "hosted_preview_tested": False,
        "browser_tested": False,
    }
    progress = Progress(report, args.output)
    progress.stage("Opening frontend port-forward")
    with kubernetes.frontend(args.timeout) as base_url:
        def fetch_config():
            status, config = request_json(base_url + "/api/contexts")
            report["latest_http_observation"] = {"observed_at": timestamp(), "path": "/api/contexts",
                                                 "status": status, "body": config}
            require(status == 200, f"Frontend configuration returned HTTP {status}")
            return config
        config = progress.wait(fetch_config, timeout=args.timeout, label="frontend configuration")
        report["configuration"] = config
        scenarios = scenarios_from_config(config, args.namespace, args.name)
        report["scenarios"] = scenarios
        progress.complete("frontend configuration")
        probe = Probe(kubernetes, base_url, scenarios, args.timeout, report, progress.checkpoint)
        report["readiness"] = progress.wait(probe.ready, timeout=args.timeout, label="all workload routing snapshots to converge")
        report["checks"].append({"name": "routing_convergence_before_publish", "passed": True})
        progress.complete("routing convergence before publishing")
        cases = []
        report["orders"] = cases
        run_id = args.name + "-" + uuid.uuid4().hex[:12]
        report["run_id"] = run_id
        progress.stage("Checking which console Pod serves each routing context, from inside the cluster")
        # No adapter is involved here: Signadot routes the browser-facing hop, so
        # this asserts the product's own routing reached the console fork. It runs
        # from a Pod because a loopback port-forward is not intercepted by DevMesh.
        probe.console_routing()
        report["checks"].append({"name": "console_fork_selected_by_signadot_routing", "passed": True})
        progress.complete("in-cluster console routing for every context")
        progress.stage("Publishing the order matrix for every routing context")
        for scenario in scenarios:
            order_id = run_id + "-" + scenario["id"]
            response = probe.api("/api/orders", key=scenario["routing_key"],
                                 data={"id": order_id, **ORDER_FIXTURE})
            total = check_checkout(response, scenario, order_id)
            cases.append({**scenario, **ORDER_FIXTURE, "order_id": order_id,
                          "total_cents": total, "checkout_response": response})
        baseline_total = cases[0]["total_cents"]
        for case in cases:
            expected_total = baseline_total * (100 - case["discount_percent"]) // 100
            require(case["total_cents"] == expected_total, f"{case['id']}: expected {case['discount_percent']}% checkout discount")
        report["matrix_effects"] = progress.wait(lambda: probe.effects(cases), timeout=args.timeout, label="processing effects for every context")
        for case in cases:
            processed = probe.api("/api/processed", key=case["routing_key"])
            records = processed.get("orders", [])
            require(any(record.get("id") == case["order_id"] for record in records),
                    f"{case['id']}: frontend did not read the selected worker ledger")
            require(all((record.get("routing_key") or "") == case["routing_key"] for record in records),
                    f"{case['id']}: frontend returned records for another routing context")
            case["frontend_processed"] = processed
        report["checks"].append({"name": "context_matrix_and_wrong_group_absence", "passed": True,
                                 "context_count": len(cases)})
        progress.complete("context matrix and wrong-group absence")

        # Republish the same producer + event ID through the real checkout.
        duplicate = cases[-1]
        report["matrix_broker_groups"] = progress.wait(probe.broker_settled, timeout=args.timeout,
                                               label="both worker groups to acknowledge the initial matrix")
        report["duplicate_before"] = probe.effects(cases)
        attempts_before = observed_attempts(report["duplicate_before"], duplicate)
        progress.stage("Republishing the combined order to check duplicate suppression")
        report["duplicate_response"] = probe.api("/api/orders", key=duplicate["routing_key"],
                                                 data={"id": duplicate["order_id"], **ORDER_FIXTURE})
        check_checkout(report["duplicate_response"], duplicate, duplicate["order_id"])
        time.sleep(args.settle_seconds)
        report["duplicate_broker_groups"] = progress.wait(probe.broker_settled, timeout=args.timeout,
                                                  label="both worker groups to acknowledge duplicate publication")
        report["duplicate_effects"] = progress.wait(lambda: probe.effects(cases), timeout=args.timeout, label="duplicate event suppression")
        attempts_after = observed_attempts(report["duplicate_effects"], duplicate)
        require(attempts_after > attempts_before, "Duplicate publication was not observed by the intended worker")
        report["duplicate_delivery_attempts"] = {"before": attempts_before, "after": attempts_after}
        report["checks"].append({"name": "duplicate_publish_one_shared_ledger_effect", "passed": True,
                                 "observation_seconds": args.settle_seconds})
        progress.complete("duplicate delivery observed with one shared-ledger effect")

        progress.stage("Publishing an order that fails its first two delivery attempts")
        retry = {**scenarios[-1], **ORDER_FIXTURE, "id": "transient-retry", "order_id": run_id + "-retry"}
        retry_response = probe.api("/api/orders", key=retry["routing_key"],
                                   data={"id": retry["order_id"], **ORDER_FIXTURE, "simulate_failures": 2})
        retry["total_cents"] = check_checkout(retry_response, retry, retry["order_id"])
        retry["checkout_response"] = retry_response
        cases.append(retry)
        report["retry_effects"] = progress.wait(lambda: probe.effects(cases), timeout=args.timeout, label="transient retry to succeed")
        retry_record = report["retry_effects"]["verified_records"][retry["order_id"]]
        require(retry_record.get("delivery_attempt", 0) >= 3, "Transient order did not demonstrate two failed delivery attempts")
        report["checks"].append({"name": "transient_failure_then_success", "passed": True})
        progress.complete("two transient failures followed by successful processing")

        progress.stage("Publishing a poison order for the intended worker dead-letter topic")
        poison = {**scenarios[-1], **ORDER_FIXTURE, "id": "poison-dlq",
                  "order_id": run_id + "-poison", "poison": True}
        poison_response = probe.api("/api/orders", key=poison["routing_key"],
                                    data={"id": poison["order_id"], **ORDER_FIXTURE, "simulate_failures": 100})
        poison["total_cents"] = check_checkout(poison_response, poison, poison["order_id"])
        poison["checkout_response"] = poison_response
        cases.append(poison)
        def poison_check():
            snapshot = probe.dlq()
            check_dead_letter(snapshot, poison)
            return snapshot
        report["dead_letters"] = progress.wait(poison_check, timeout=args.timeout, label="poison message in intended worker DLQ")
        report["checks"].append({"name": "poison_event_in_only_intended_group_dlq", "passed": True})
        progress.complete("poison message in only the intended worker dead-letter topic")

        schema_cases = schema_rejection_cases(scenarios, run_id)
        report["schema_rejection_cases"] = schema_cases
        cases.extend(schema_cases)
        progress.stage("Publishing two incompatible schemas with valid CloudEvent context")
        for case in schema_cases:
            probe.publish_schema_event(case)
        report["schema_rejection_broker_groups"] = progress.wait(
            probe.broker_settled, timeout=args.timeout,
            label="both worker groups to acknowledge schema-rejected events")
        # Dapr v1.18.3 subscription.go:365-375 sends an app DROP to its configured
        # DLQ, then ACKs; non-owners must return SUCCESS before business validation.
        report["schema_rejection_effects"] = progress.wait(
            lambda: probe.schema_rejections(schema_cases), timeout=args.timeout,
            label="schema rejection only in each selected owner's DLQ, without ledger effects")
        report["checks"].append({"name": "business_schema_rejected_only_by_selected_owner", "passed": True,
                                 "contexts": ["baseline", "combined"], "published_events": 2})
        progress.complete("both groups acknowledged incompatible schemas; only owners dead-lettered, with no effects")

        progress.stage("Submitting a malformed routing key and checking final absence of unintended effects")
        malformed_id = run_id + "-malformed"
        status, body = request_json(base_url + "/api/orders", key="invalid key", data={"id": malformed_id, **ORDER_FIXTURE})
        report["malformed_routing_key"] = {"status": status, "body": body, "order_id": malformed_id}
        # A malformed key fails header parsing before any route lookup, so the route cache's
        # freshness cannot change the answer: this is a deterministic 400, never a 503.
        # Accepting 503 here would have let an unknown-key resolution failure pass as if it
        # were input rejection. Three live runs recorded 400.
        require(status == 400, f"Malformed routing key was not rejected with HTTP 400 (got {status})")
        cases.append({**scenarios[0], **ORDER_FIXTURE, "id": "malformed-routing-key",
                      "order_id": malformed_id, "poison": True})
        time.sleep(args.settle_seconds)
        report["final_broker_groups"] = progress.wait(probe.broker_settled, timeout=args.timeout,
                                              label="both worker groups to acknowledge all published events")
        report["final_effects"] = progress.wait(lambda: probe.effects(cases), timeout=args.timeout, label="final effects and no poison/malformed processing")
        report["checks"].append({"name": "malformed_routing_key_rejected_without_effect", "passed": True})
        report["checks"].append({"name": "all_pods_inspected_and_unintended_group_effects_absent", "passed": True,
                                 "observation_seconds": args.settle_seconds})
        progress.complete("final effects and malformed-key rejection")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", default="minikube")
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--name", required=True, help="Bootstrap sandbox name prefix")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=120, help="Seconds per convergence or processing phase")
    parser.add_argument("--settle-seconds", type=float, default=5,
                        help="Finite observation window after duplicate and rejected submissions")
    args = parser.parse_args(argv)
    if args.timeout <= 0 or args.settle_seconds < 1:
        parser.error("--timeout must be positive and --settle-seconds at least 1")
    report = {"kind": "real-cluster-acceptance", "started_at": timestamp(),
              "context": args.context, "namespace": args.namespace, "name": args.name,
              "checks": [], "passed": False,
              "scope": "Application namespace only; no control-plane reinstall, replica changes, Pod replacement or deletion.",
              "limitation": "Exactly-one effect means one atomic Redis demo ledger record per source/event ID during this observation; external side effects are not tested."}
    exit_code = 1
    try:
        verify(args, report)
        report["passed"] = True
        exit_code = 0
    except KeyboardInterrupt:
        report["error"] = "Interrupted"
        exit_code = 130
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    finally:
        report["finished_at"] = timestamp()
        write_report(args.output, report)
    print(f"{'PASS' if report['passed'] else 'FAIL'}: {len(report['checks'])} completed checks; evidence: {args.output}")
    if report.get("error"):
        print(report["error"], file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
