#!/usr/bin/env python3
"""Provision the Dapr tutorial in one explicitly selected local cluster.

Minikube is the documented target; Docker Desktop's Kubernetes also works. Only
Python's standard library is required. Commands never invoke a shell, read
Kubernetes Secrets, change kubeconfig, or modify installed control planes or
cluster-wide policy: the admission rule in k8s/dapr-fork-service-label.yaml is a
prerequisite that `doctor` checks for. The local state directory is the
ownership receipt: keep it until `down` succeeds.
"""
from __future__ import annotations

import argparse
import copy
from contextlib import contextmanager
import datetime as dt
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

try:
    import fcntl
except ImportError:  # Native Windows lacks POSIX receipt locking.
    fcntl = None

ROOT = Path(__file__).resolve().parents[1]


def _load_naming_rule():
    """Load the app-ID naming rule from the adapter itself, so both always agree.

    appid.py is standard library only; loading the file directly avoids importing
    the rest of the adapter package and its HTTP dependencies.
    """
    spec = importlib.util.spec_from_file_location("appid", ROOT / "app" / "signadot" / "appid.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.fork_app_id


fork_app_id = _load_naming_rule()
OWNER = "tutorial.signadot.com/owner"
APP_IDS = ("frontend", "checkout", "order-processor")
# Every forkable role. The console is forked like any other workload; ordinary
# Signadot routing reaches it, because a browser calls it over plain HTTP.
ROLES = {"frontend": "frontend", "checkout": "checkout", "processor": "order-processor"}
# Only roles that are addressed by native Dapr invocation need to be reachable as
# `<app-id>-dapr`. Nothing invokes the console.
INVOCATION_ROLES = ("checkout", "processor")
# A fork only sets `dapr.io/app-id`. Dapr's injector gives it a current daprd under
# that app ID, and Dapr's operator creates its `<app-id>-dapr` Service. The
# cluster-wide admission rule labels that Service with the fork's own
# forked-workload-id, so the Signadot Operator does not mistake it for a baseline
# Service. See k8s/dapr-fork-service-label.yaml.
ADMISSION_POLICY = "dapr-fork-service-label"
FORK_LABEL = "signadot.com/forked-workload-id"
MIN_KUBERNETES = (1, 36)
# One environment override per role makes each fork observably different.
CUSTOMIZATIONS = {"frontend": {"name": "CONSOLE_VARIANT", "value": "sandbox"},
                  "checkout": {"name": "DISCOUNT_PERCENT", "value": "10"},
                  "processor": {"name": "FULFILLMENT_MODE", "value": "priority"}}
# Preview endpoints are served by Signadot's control plane, which injects this
# sandbox's routing key into every request made through the returned URL.
PREVIEW_ENDPOINT = "console"


def preview_endpoints(namespace):
    """A hosted entry point for each sandbox and for the RouteGroup.

    The target is always the baseline console Service. Signadot injects the
    routing key, so the request reaches the console fork when the sandbox forks
    it, and the baseline console otherwise; either way the key continues to
    select checkout and the worker further down the chain.
    """
    return [{"name": PREVIEW_ENDPOINT, "target": f"http://frontend.{namespace}.svc:8080"}]


def endpoint_urls(obj):
    """Preview URLs reported by the control plane for a sandbox or RouteGroup."""
    found = {}
    for endpoint in (obj or {}).get("endpoints") or []:
        name, url = endpoint.get("name"), endpoint.get("url")
        if isinstance(name, str) and isinstance(url, str) and url:
            found[name] = url
    return found


class TutorialError(RuntimeError):
    """An actionable precondition or convergence failure."""


@contextmanager
def state_lock(args):
    """Serialize receipt creation and all command writes across local processes."""
    if fcntl is None:
        raise TutorialError("This tutorial requires POSIX file locking and supports macOS or Linux hosts. "
                            "Native Windows is unsupported; run the commands on macOS or Linux. "
                            "WSL2 has not been validated for this tutorial.")
    directory = args.state_dir.resolve() / args.name
    directory.mkdir(parents=True, exist_ok=True)
    lock_path = directory / ".lock"
    with lock_path.open("a+") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise TutorialError(f"Another tutorial command is using {directory}; wait for it to finish before retrying") from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def owned(obj, owner):
    return obj.get("metadata", {}).get("labels", {}).get(OWNER) == owner


def require_owned(obj, owner):
    if not owned(obj, owner):
        raise TutorialError(f"Refusing foreign {obj.get('kind', 'object')} "
                            f"{obj.get('metadata', {}).get('name', '?')}: ownership label differs")


def signadot_owned(obj, owner, cluster, kind):
    spec = obj.get("spec", {})
    if spec.get("cluster") != cluster:
        return False
    if kind == "sandbox":
        return spec.get("labels", {}).get(OWNER) == owner
    return (spec.get("description") == f"Managed by dapr-tutorial; owner={owner}"
            and spec.get("match") == {"label": {"key": OWNER, "value": owner}})


def contains_desired(actual, desired):
    """Compare only specified fields, tolerating API defaults and patch key order."""
    if isinstance(desired, dict):
        return isinstance(actual, dict) and all(k in actual and contains_desired(actual[k], v) for k, v in desired.items())
    if isinstance(desired, list):
        return isinstance(actual, list) and len(actual) == len(desired) and all(contains_desired(a, d) for a, d in zip(actual, desired))
    if isinstance(desired, str) and isinstance(actual, str) and desired.startswith("{"):
        try:
            return json.loads(actual) == json.loads(desired)
        except ValueError:
            pass
    return actual == desired


def sandbox_name(name, role):
    return f"{name}-{role}"


def fork_app_ids(name, namespace):
    """The app ID each role's fork runs under, from the same rule callers apply."""
    return {role: fork_app_id(sandbox_name(name, role), "Deployment", namespace, baseline)
            for role, baseline in ROLES.items()}


def metadata(name, namespace, owner, **extra):
    result = {"name": name, "namespace": namespace, "labels": {OWNER: owner}}
    result.update(extra)
    return result


def redis_manifests(namespace, owner):
    meta = lambda name: metadata(name, namespace, owner)
    return [
        {"apiVersion": "v1", "kind": "PersistentVolumeClaim", "metadata": meta("redis-data"),
         "spec": {"accessModes": ["ReadWriteOnce"], "resources": {"requests": {"storage": "1Gi"}}}},
        {"apiVersion": "v1", "kind": "Service", "metadata": meta("redis"),
         "spec": {"selector": {"app": "redis"}, "ports": [{"port": 6379, "targetPort": 6379}]}},
        {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": meta("redis"),
         "spec": {"replicas": 1, "strategy": {"type": "Recreate"},
                  "selector": {"matchLabels": {"app": "redis"}}, "template": {
                      "metadata": {"labels": {"app": "redis", OWNER: owner}}, "spec": {
                          "containers": [{"name": "redis", "image": "redis:7.4-alpine@sha256:ff02b58f971e7d7d156a1267e283fcbbeee91773b6aa36c49dac28ecfe28eadf",
                                          "args": ["redis-server", "--appendonly", "yes", "--appendfsync", "always"],
                                          "ports": [{"containerPort": 6379}],
                                          "readinessProbe": {"exec": {"command": ["redis-cli", "ping"]}, "periodSeconds": 2},
                                          "volumeMounts": [{"name": "data", "mountPath": "/data"}]}],
                          "volumes": [{"name": "data", "persistentVolumeClaim": {"claimName": "redis-data"}}]}}}}]


def dapr_manifests(namespace, owner):
    # No `scopes`: a scope list names app IDs up front, and a sandbox created later by a
    # pull request or an agent would be missing from it. The namespace is the boundary.
    return [{"apiVersion": "dapr.io/v1alpha1", "kind": "Component",
             "metadata": metadata("pubsub", namespace, owner),
             "spec": {"type": "pubsub.redis", "version": "v1", "metadata": [
                 {"name": "redisHost", "value": "redis:6379"}, {"name": "redisPassword", "value": ""},
                 {"name": "consumerID", "value": "{appID}"},
                 {"name": "processingTimeout", "value": "10s"}, {"name": "redeliverInterval", "value": "1s"}]}},
            {"apiVersion": "dapr.io/v1alpha1", "kind": "Resiliency",
             "metadata": metadata("pubsub-retries", namespace, owner),
             "spec": {"policies": {"retries": {"inbound": {"policy": "constant", "duration": "1s", "maxRetries": 3}}},
                      "targets": {"components": {"pubsub": {"inbound": {"retry": "inbound"}}}}}}]


def application_manifests(namespace, owner, image, service_account="default"):
    result = []
    for role in APP_IDS:
        # DevMesh is injected on every baseline, including the console: a browser
        # reaches it over ordinary HTTP, which is exactly what DevMesh routes.
        annotations = {"dapr.io/enabled": "true", "dapr.io/app-id": role, "dapr.io/app-port": "8080",
                       "dapr.io/sidecar-svc-annotations": "routing.signadot.com/ignore=true",
                       "sidecar.signadot.com/inject": "true"}
        # The baseline app IDs are the only app IDs any service is configured with.
        # Forks get theirs from the naming rule, so a new sandbox needs no change here.
        env = {"BASELINE_NAME": role,
               "BASELINE_NAMESPACE": namespace, "FRONTEND_BASELINE_NAME": "frontend",
               "CHECKOUT_BASELINE_NAME": "checkout",
               "PROCESSOR_BASELINE_NAME": "order-processor", "FRONTEND_APP_ID": "frontend",
               "CHECKOUT_APP_ID": "checkout", "PROCESSOR_APP_ID": "order-processor",
               "REDIS_URL": "redis://redis:6379/0",
               "PUBSUB_NAME": "pubsub", "ORDERS_TOPIC": "orders", "DISCOUNT_PERCENT": "0",
               "FULFILLMENT_MODE": "standard", "CONSOLE_VARIANT": "baseline"}
        app = {"name": "app", "image": image, "imagePullPolicy": "IfNotPresent",
               "command": ["uvicorn", f"{role.replace('-', '_')}.main:app", "--host", "0.0.0.0", "--port", "8080"],
               "ports": [{"containerPort": 8080, "name": "http"}],
               "env": [{"name": k, "value": v} for k, v in env.items()] + [{"name": "DAPR_APP_ID", "valueFrom": {
                   "fieldRef": {"fieldPath": "metadata.annotations['dapr.io/app-id']"}}}],
               "readinessProbe": {"httpGet": {"path": "/readyz", "port": 8080},
                                  "periodSeconds": 10, "timeoutSeconds": 10, "failureThreshold": 3}}
        result.append({"apiVersion": "apps/v1", "kind": "Deployment", "metadata": metadata(role, namespace, owner),
                       "spec": {"replicas": 1, "selector": {"matchLabels": {"app": role}}, "template": {
                           "metadata": {"labels": {"app": role, OWNER: owner}, "annotations": annotations},
                           "spec": {"serviceAccountName": service_account, "containers": [app]}}}})
        ports = [{"name": "http", "port": 8080, "targetPort": 8080}]
        result.append({"apiVersion": "v1", "kind": "Service", "metadata": metadata(role, namespace, owner),
                       "spec": {"selector": {"app": role}, "ports": ports}})
    return result


def sandbox_manifest(name, role, namespace, owner, cluster, image):
    """The sandbox spec for one role's fork: pure data, nothing read from the cluster.

    The image, one environment override, and the app ID from the naming rule. A CI
    job or an agent can produce the same spec with the Signadot CLI alone; see
    k8s/pr-sandbox.yaml.
    """
    sandbox = sandbox_name(name, role)
    app_id = fork_app_id(sandbox, "Deployment", namespace, ROLES[role])
    # dapr.io/enabled stays "true" from the baseline. Dapr's injector gives the fork a
    # current daprd under the new app ID, and Dapr's operator creates its
    # `<app-id>-dapr` Service, selecting only this fork's Pods.
    patch = {"spec": {"template": {"metadata": {"annotations": {"dapr.io/app-id": app_id}},
                                   "spec": {"containers": [{"name": "app", "image": image,
                                                            "env": [CUSTOMIZATIONS[role]]}]}}}}
    return {"name": sandbox, "spec": {"cluster": cluster,
        "description": "Dapr tutorial fork with native mTLS and unique app identity",
        "labels": {OWNER: owner},
        "defaultRouteGroup": {"endpoints": preview_endpoints(namespace)},
        "forks": [{"forkOf": {"kind": "Deployment", "namespace": namespace, "name": ROLES[role]},
            "customizations": {"patch": {"type": "strategic", "value": json.dumps(patch)}}}]}}


def dapr_service(items, sandbox, app_id, baseline):
    """Confirm the `<app-id>-dapr` Service Dapr created serves exactly this fork."""
    key = sandbox["routingKey"]
    deployments = [i for i in items if i["kind"] == "Deployment"
                   and i["metadata"].get("labels", {}).get("signadot.com/sandbox-routing-key") == key
                   and i["metadata"].get("annotations", {}).get("signadot.com/workload-name") == baseline]
    if len(deployments) != 1:
        raise TutorialError(f"Expected one current fork Deployment for {sandbox['name']}")
    dep = deployments[0]
    if dep["spec"]["template"]["metadata"]["annotations"].get("dapr.io/app-id") != app_id:
        raise TutorialError(f"Fork {dep['metadata']['name']} has an unexpected Dapr app ID")
    services = [i for i in items if i["kind"] == "Service" and i["metadata"]["name"] == app_id + "-dapr"]
    if len(services) != 1:
        raise TutorialError(f"Dapr has not created {app_id}-dapr yet")
    svc = services[0]
    if not any(ref.get("kind") == "Deployment" and ref.get("uid") == dep["metadata"]["uid"]
               for ref in svc["metadata"].get("ownerReferences", [])):
        raise TutorialError(f"{app_id}-dapr is not owned by fork Deployment {dep['metadata']['name']}")
    selector = svc["spec"].get("selector") or {}
    if selector != dep["spec"]["selector"].get("matchLabels"):
        raise TutorialError(f"{app_id}-dapr does not select exactly the fork's Pods")
    if svc["metadata"].get("labels", {}).get(FORK_LABEL) != selector.get(FORK_LABEL):
        raise TutorialError(f"{app_id}-dapr lacks the {FORK_LABEL} label the admission rule adds; "
                            f"check that k8s/dapr-fork-service-label.yaml is applied, then run reconcile")
    return {"name": svc["metadata"]["name"], "deployment": dep["metadata"]["name"],
            "selector": selector}


def pod_ready(pod, containers):
    if pod.get("metadata", {}).get("deletionTimestamp"):
        return False
    statuses = {c["name"]: c.get("ready", False) for c in pod.get("status", {}).get("containerStatuses", [])}
    return all(statuses.get(c, False) for c in containers) and all(statuses.values())


def current_baseline_pods(deployment, replica_sets, pods, image):
    """Exclude the previous rollout's Ready Pods when generating a new fork.

    A current ReplicaSet must belong to this Deployment and contain the complete
    desired Pod template. Pod readiness alone is insufficient during an update.
    """
    if deployment.get("status", {}).get("observedGeneration", 0) < deployment["metadata"].get("generation", 1):
        return []
    template = deployment["spec"]["template"]
    desired_app = next((c for c in template["spec"]["containers"] if c["name"] == "app"), {})
    if desired_app.get("image") != image:
        return []

    def canonical(value):
        value = copy.deepcopy(value)
        meta = value.setdefault("metadata", {})
        meta.pop("creationTimestamp", None)
        meta.setdefault("labels", {}).pop("pod-template-hash", None)
        return value

    current = set()
    for rs in replica_sets:
        if rs["metadata"].get("deletionTimestamp"):
            continue
        if not any(ref.get("kind") == "Deployment" and ref.get("uid") == deployment["metadata"]["uid"]
                   for ref in rs["metadata"].get("ownerReferences", [])):
            continue
        if canonical(rs["spec"]["template"]) == canonical(template):
            current.add(rs["metadata"]["uid"])
    return [pod for pod in pods if not pod["metadata"].get("deletionTimestamp")
            and any(ref.get("kind") == "ReplicaSet" and ref.get("uid") in current
                    for ref in pod["metadata"].get("ownerReferences", []))
            and next((c.get("image") for c in pod["spec"]["containers"] if c["name"] == "app"), None) == image]


class Tutorial:
    def __init__(self, args):
        self.args = args
        self.directory = args.state_dir.resolve() / args.name
        self.path = self.directory / "state.json"
        self.state = json.loads(self.path.read_text()) if self.path.exists() else None
        if self.state:
            for field in ("name", "namespace", "context", "cluster"):
                if self.state.get(field) != getattr(args, field):
                    raise TutorialError(f"State {field} differs; use the original values or another --state-dir")
        self.owner = self.state["owner"] if self.state else str(uuid.uuid4())

    def log(self, message):
        print(message, file=sys.stderr, flush=True)

    def run(self, command, *, timeout=None):
        result = subprocess.run(command, text=True, capture_output=True, timeout=timeout or min(self.args.timeout, 60))
        if result.returncode:
            raise TutorialError(f"Command failed: {' '.join(command[:6])}\n{result.stderr.strip()}")
        return result.stdout

    def kube(self, *args):
        return self.run(["kubectl", "--context", self.args.context, "--request-timeout=30s", *args])

    def get(self, kind, name=None, namespaced=True):
        args = ["get", kind]
        if name:
            args.extend([name, "--ignore-not-found"])
        if namespaced:
            args.extend(["-n", self.args.namespace])
        value = self.kube(*args, "-o", "json")
        return json.loads(value) if value.strip() else None

    def save(self, **updates):
        if self.state is None:
            self.state = {"name": self.args.name, "namespace": self.args.namespace,
                          "context": self.args.context, "cluster": self.args.cluster,
                          "owner": self.owner, "createdAt": stamp(), "stateDir": str(self.directory), "actions": []}
        self.state.update(updates)
        if updates.get("phase") in {"ready", "deleted"}:
            self.state.pop("lastError", None)
            self.state.pop("failedAt", None)
        self.state["updatedAt"] = stamp()
        write_json(self.path, self.state)

    def namespace(self, create=False):
        ns = self.get("namespace", self.args.namespace, False)
        if ns:
            if self.state is None:
                raise TutorialError("Namespace exists but the local ownership receipt is missing; refusing adoption")
            require_owned(ns, self.owner)
        elif create:
            self.save(phase="creating-namespace")
            obj = {"apiVersion": "v1", "kind": "Namespace", "metadata": {
                "name": self.args.namespace, "labels": {OWNER: self.owner}}}
            path = self.directory / "manifests" / "namespace.json"
            write_json(path, obj)
            self.kube("create", "-f", str(path))
            ns = self.get("namespace", self.args.namespace, False)
            require_owned(ns, self.owner)
        return ns

    def apply(self, objects, filename):
        self.namespace()
        for obj in objects:
            old = self.get(obj["kind"], obj["metadata"]["name"])
            if old:
                require_owned(old, self.owner)
        path = self.directory / "manifests" / filename
        write_json(path, {"apiVersion": "v1", "kind": "List", "items": objects})
        self.kube("apply", "-f", str(path))

    def account_object(self, kind, name):
        objects = json.loads(self.run(["signadot", kind, "list", "-o", "json"]))
        if not isinstance(objects, list):
            raise TutorialError(f"Unexpected Signadot {kind} list response")
        matches = [obj for obj in objects if obj["name"] == name]
        if len(matches) > 1:
            raise TutorialError(f"Ambiguous Signadot {kind} name {name}")
        if matches and not signadot_owned(matches[0], self.owner, self.args.cluster, kind):
            raise TutorialError(f"Refusing foreign Signadot {kind} {name}: cluster or ownership marker differs")
        return matches[0] if matches else None

    def apply_account(self, kind, obj):
        old = self.account_object(kind, obj["name"])
        path = self.directory / "manifests" / f"{obj['name']}-{kind}.json"
        write_json(path, obj)
        if old and contains_desired(old.get("spec", {}), obj["spec"]):
            return
        self.run(["signadot", kind, "apply", "-f", str(path), "--wait=false", "-o", "json"])

    def docker_desktop(self):
        return self.args.context == "docker-desktop"

    def check_local(self):
        tools = ("kubectl", "signadot") if self.docker_desktop() else ("kubectl", "minikube", "signadot")
        for tool in tools:
            if not shutil.which(tool):
                raise TutorialError(f"Install {tool} before running the tutorial")
        if self.docker_desktop():
            nodes = self.get("nodes", namespaced=False)["items"]
            names = [n["metadata"]["name"] for n in nodes]
            if not names or any(n != "docker-desktop" and not n.startswith("desktop-") for n in names):
                raise TutorialError("kubectl context docker-desktop does not point at Docker Desktop's cluster")
            return
        local = json.loads(self.run(["minikube", "status", "-p", self.args.context, "-o", "json"]))
        if any(local.get(k) != "Running" for k in ("Host", "Kubelet", "APIServer")):
            raise TutorialError("The explicitly selected Minikube profile is not running")
        nodes = self.get("nodes", namespaced=False)["items"]
        if not nodes or any(n["metadata"].get("labels", {}).get("minikube.k8s.io/name") != self.args.context for n in nodes):
            raise TutorialError("kubectl context does not point at the selected local Minikube profile")

    def storage_preflight(self):
        """Inspect default-class configuration; actual provisioning is checked by up."""
        try:
            classes = self.get("storageclasses.storage.k8s.io", namespaced=False)["items"]
        except TutorialError as exc:
            raise TutorialError("Cannot inspect the default StorageClass. The selected Kubernetes identity needs "
                                f"list access to storageclasses.storage.k8s.io on context {self.args.context}. "
                                f"Check with: kubectl --context {self.args.context} get storageclasses\n{exc}") from exc
        defaults = [item for item in classes if not item["metadata"].get("deletionTimestamp")
                    and any(item["metadata"].get("annotations", {}).get(annotation) == "true" for annotation in
                            ("storageclass.kubernetes.io/is-default-class", "storageclass.beta.kubernetes.io/is-default-class"))]
        if not defaults:
            raise TutorialError("No default StorageClass is configured. The tutorial's Redis PVC requires automatic "
                                "volume provisioning. Configure a default dynamic StorageClass in the selected "
                                f"local Minikube profile {self.args.context}, then rerun doctor. "
                                "Doctor does not enable storage addons or create storage resources.")
        # Kubernetes chooses the newest default when several exist. An older
        # working class must not hide a newly selected, unusable default.
        newest = max(item["metadata"].get("creationTimestamp", "") for item in defaults)
        selected = [item for item in defaults if item["metadata"].get("creationTimestamp", "") == newest]
        if len(selected) != 1:
            raise TutorialError("Several default StorageClasses have the same creation timestamp. "
                                "Leave one intended default dynamic StorageClass before running this tutorial.")
        default = selected[0]
        name, provisioner = default["metadata"]["name"], default.get("provisioner")
        if not provisioner or provisioner == "kubernetes.io/no-provisioner":
            raise TutorialError(f"Default StorageClass {name!r} does not provide automatic volume provisioning. "
                                "This tutorial creates a Redis PVC without a pre-created PersistentVolume. "
                                "Configure a default dynamic StorageClass in the selected local Minikube profile.")
        binding = default.get("volumeBindingMode", "Immediate")
        if binding not in {"Immediate", "WaitForFirstConsumer"}:
            raise TutorialError(f"Default StorageClass {name!r} has unsupported volumeBindingMode {binding!r}")
        return {"defaultClass": name, "provisioner": provisioner, "volumeBindingMode": binding,
                "defaultClasses": sorted(item["metadata"]["name"] for item in defaults),
                "verification": "Configuration inspected only; up separately waits for Redis/PVC readiness."}

    def permission_preflight(self):
        """Ask authorization about concrete lifecycle/verification actions; grant nothing."""
        checks = [(verb, "namespaces" + ("/" + self.args.namespace if verb != "create" else ""), None)
                  for verb in ("get", "create", "delete")]
        for resource in ("deployments.apps", "services", "persistentvolumeclaims",
                         "components.dapr.io", "resiliencies.dapr.io"):
            checks.extend((verb, resource, None) for verb in ("get", "create", "patch"))
        checks.extend(("list", resource, None) for resource in ("deployments.apps", "replicasets.apps", "services", "pods"))
        checks.extend([("get", "pods", None), ("delete", "pods", None)])
        # Both verbs cover the WebSocket handshake and the create authorization
        # used for streaming connections, including the SPDY fallback.
        checks.extend((verb, "pods", subresource) for subresource in ("exec", "portforward") for verb in ("get", "create"))
        confirmed = []
        for verb, resource, subresource in checks:
            arguments = ["auth", "can-i", verb, resource, "--namespace", self.args.namespace]
            if subresource:
                arguments.extend(["--subresource", subresource])
            command = " ".join(["kubectl", "--context", self.args.context, *arguments])
            permission = f"{verb} {resource}" + (f"/{subresource}" if subresource else "")
            try:
                answer = self.kube(*arguments).strip()
            except TutorialError as exc:
                raise TutorialError(f"Required Kubernetes permission {permission!r} was denied or could not be checked. "
                                    f"Use an identity authorized for this tutorial in namespace {self.args.namespace}. "
                                    f"Diagnose with: {command}\n{exc}") from exc
            if answer != "yes":
                raise TutorialError(f"Required Kubernetes permission {permission!r} is not allowed in namespace "
                                    f"{self.args.namespace}. Use an authorized identity, then rerun doctor. "
                                    f"Diagnose with: {command}")
            confirmed.append({"verb": verb, "resource": resource, "subresource": subresource, "allowed": True})
        return {"namespace": self.args.namespace, "checks": confirmed,
                "verification": "Authorization checks only; admission policies and actual operations may still reject requests."}

    def admission_preflight(self):
        """Kubernetes 1.36 or later, with the admission rule that lets Dapr inject forks."""
        server = json.loads(self.kube("version", "-o", "json"))["serverVersion"]
        version = (int(server["major"]), int(re.match(r"\d+", server["minor"]).group()))
        if version < MIN_KUBERNETES:
            raise TutorialError(f"Kubernetes {version[0]}.{version[1]} is too old. This tutorial needs 1.36 or later, "
                                "where MutatingAdmissionPolicy is generally available.")
        group = "admissionregistration.k8s.io"
        policy = self.get("mutatingadmissionpolicies." + group, ADMISSION_POLICY, False)
        binding = self.get("mutatingadmissionpolicybindings." + group, ADMISSION_POLICY, False)
        if not policy or not binding or binding.get("spec", {}).get("policyName") != ADMISSION_POLICY:
            raise TutorialError(f"The admission rule {ADMISSION_POLICY} is not installed. It lets Dapr's injector "
                                "give each fork its own sidecar. Apply it once per cluster with: "
                                f"kubectl --context {self.args.context} apply -f k8s/dapr-fork-service-label.yaml")
        return {"kubernetes": f"{version[0]}.{version[1]}", "policy": ADMISSION_POLICY,
                "label": FORK_LABEL}

    def repair_fork_services(self):
        """Restart a fork whose Dapr Service lacks the rule's label, so Dapr rewrites it.

        Dapr rewrites its Service only when the fork's Deployment changes. If the rule
        was missing at that moment, the Service lost its label and Signadot rejects the
        fork until the next rewrite. Restarting the fork's Pod triggers one.
        """
        keys = {s["routingKey"] for s in (self.account_object("sandbox", sandbox_name(self.args.name, role))
                                          for role in ROLES) if s and s.get("routingKey")}
        for svc in self.get("services")["items"]:
            meta, selector = svc["metadata"], svc["spec"].get("selector") or {}
            labels = meta.get("labels", {})
            if (labels.get("dapr.io/enabled") == "true" and FORK_LABEL in selector and FORK_LABEL not in labels
                    and selector.get("signadot.com/sandbox-routing-key") in keys):
                self.log(f"{meta['name']} lacks its {FORK_LABEL} label; restarting the fork's Pod so Dapr rewrites it")
                pods = ",".join(f"{k}={v}" for k, v in sorted(selector.items()))
                self.kube("delete", "pods", "-n", self.args.namespace, "-l", pods, "--wait=false")

    def doctor(self):
        self.check_local()
        storage = self.storage_preflight()
        permissions = self.permission_preflight()
        admission = self.admission_preflight()
        versions = {"localCluster": "docker-desktop" if self.docker_desktop()
                    else self.run(["minikube", "version", "--short"]).strip(),
                    "signadotCLI": self.run(["signadot", "--version"]).strip(),
                    "kubernetes": json.loads(self.kube("version", "-o", "json")), "capturedAt": stamp(),
                    "preflight": {"storage": storage, "kubernetesPermissions": permissions,
                                  "admissionRule": admission}}
        clusters = json.loads(self.run(["signadot", "cluster", "list", "-o", "json"]))
        selected = [c for c in clusters if c["name"] == self.args.cluster]
        if len(selected) != 1 or not selected[0].get("operator", {}).get("version"):
            raise TutorialError("Selected Signadot cluster is missing or has no connected operator")
        versions["signadotCluster"] = selected[0]
        versions["preflight"]["clusterMapping"] = {
            "kubernetesContext": self.args.context, "signadotCluster": self.args.cluster,
            "verifiedAutomatically": False,
            "verification": "Confirm the cluster name from this operator installation's Dashboard registration. "
                            "These endpoints are checked independently; a mismatched name sends Signadot API "
                            "operations to another cluster."}
        self.log(f"Cluster mapping: context {self.args.context!r} / Signadot {self.args.cluster!r}; "
                 "use the matching Dashboard registration (not automatically verified).")
        for namespace in ("dapr-system", "signadot"):
            deps = json.loads(self.kube("get", "deployments", "-n", namespace, "-o", "json"))["items"]
            if not deps or any(d.get("status", {}).get("availableReplicas", 0) < 1 for d in deps):
                raise TutorialError(f"Install and ready the {namespace} control plane first")
            versions[namespace] = [{"name": d["metadata"]["name"],
                                   "images": [c["image"] for c in d["spec"]["template"]["spec"]["containers"]]} for d in deps]
        for kind in ("components.dapr.io", "resiliencies.dapr.io", "forkedworkloads.signadot.com"):
            if not self.get("customresourcedefinition", kind, False):
                raise TutorialError(f"Required CRD {kind} is absent")
        # Lists are read-only and establish account access without reading credentials.
        for role in ROLES:
            self.account_object("sandbox", f"{self.args.name}-{role}")
        self.account_object("routegroup", f"{self.args.name}-combined")
        self.namespace()
        write_json(self.directory / "evidence" / "versions.json", versions)
        return versions

    def wait(self, description, callback):
        self.log(f"Waiting for {description} (up to {self.args.timeout}s)…")
        deadline, last_error = time.monotonic() + self.args.timeout, None
        while time.monotonic() < deadline:
            try:
                value = callback()
                if value:
                    return value
            except TutorialError as exc:
                last_error = str(exc)
            time.sleep(2)
        raise TutorialError(f"Timed out waiting for {description}" + (f": {last_error}" if last_error else ""))

    def baseline_pods(self):
        items = self.get("deployments,replicasets,pods")["items"]
        pods = [i for i in items if i["kind"] == "Pod"]
        replica_sets = [i for i in items if i["kind"] == "ReplicaSet"]
        deployments = {i["metadata"]["name"]: i for i in items if i["kind"] == "Deployment"}
        selected = {}
        for role in APP_IDS:
            deployment = deployments.get(role)
            if not deployment:
                continue
            require_owned(deployment, self.owner)
            candidates = current_baseline_pods(deployment, replica_sets, pods, self.state["image"])
            for pod in candidates:
                required = ["app", "daprd", "sd-sidecar"]
                if pod_ready(pod, required):
                    selected[role] = pod
                    break
            if role not in selected and candidates:
                ready_without_mesh = any(pod_ready(p, ["app", "daprd"]) and
                                         "sd-sidecar" not in {c["name"] for c in p["spec"]["containers"]}
                                         for p in candidates)
                action = "recover-devmesh-" + role
                if ready_without_mesh and action not in self.state["actions"]:
                    self.state["actions"].append(action)
                    self.save()
                    self.log(f"Baseline {role} missed DevMesh admission; performing one owned rollout restart")
                    self.kube("rollout", "restart", "deployment/" + role, "-n", self.args.namespace)
        return selected if len(selected) == len(APP_IDS) else None

    def up(self):
        if not self.args.image:
            raise TutorialError("up requires --image, built and loaded into the selected local cluster")
        self.doctor()
        self.namespace(create=True)
        self.save(phase="redis", image=self.args.image)
        self.apply(redis_manifests(self.args.namespace, self.owner), "redis.json")
        self.wait("Redis persistence and readiness", lambda: any(
            pod_ready(p, ["redis"]) for p in self.get("pods")["items"] if p["metadata"].get("labels", {}).get("app") == "redis"))
        self.save(phase="baselines")
        self.apply(dapr_manifests(self.args.namespace, self.owner), "dapr.json")
        self.apply(application_manifests(self.args.namespace, self.owner, self.args.image,
                                         self.args.service_account), "applications.json")
        self.wait("baseline apps, Dapr mTLS sidecars and DevMesh injection", self.baseline_pods)
        self.save(phase="sandboxes")
        for role in ROLES:
            self.apply_account("sandbox", sandbox_manifest(self.args.name, role, self.args.namespace,
                               self.owner, self.args.cluster, self.args.image))
        self.apply_account("routegroup", {"name": f"{self.args.name}-combined", "spec": {
            "cluster": self.args.cluster, "description": f"Managed by dapr-tutorial; owner={self.owner}",
            "match": {"label": {"key": OWNER, "value": self.owner}},
            "endpoints": preview_endpoints(self.args.namespace)}})
        return self.reconcile()

    def reconcile(self):
        self.check_local()
        if self.state is None or not self.namespace():
            raise TutorialError("No owned tutorial namespace; run up first")
        self.admission_preflight()
        self.save(phase="reconciling")
        self.repair_fork_services()
        def ready_sandboxes():
            found = {role: self.account_object("sandbox", f"{self.args.name}-{role}") for role in ROLES}
            if all(s and s.get("status", {}).get("ready") and s.get("routingKey")
                   and endpoint_urls(s).get(PREVIEW_ENDPOINT) for s in found.values()):
                return found
            return None
        sandboxes = self.wait("Signadot sandboxes and their console preview URLs", ready_sandboxes)
        app_ids = fork_app_ids(self.args.name, self.args.namespace)
        def dapr_services_ready():
            items = self.get("deployments,services")["items"]
            return [dapr_service(items, sandboxes[role], app_ids[role], ROLES[role])
                    for role in INVOCATION_ROLES]
        native = self.wait("Dapr's own Services for the forks", dapr_services_ready)
        def routegroup_ready():
            rg = self.account_object("routegroup", f"{self.args.name}-combined")
            expected = {s["name"] for s in sandboxes.values()}
            if (rg and rg.get("routingKey") and set(rg.get("status", {}).get("matchedSandboxes", [])) == expected
                    and endpoint_urls(rg).get(PREVIEW_ENDPOINT)):
                return rg
            return None
        rg = self.wait("RouteGroup membership and console preview URL", routegroup_ready)
        self.save(sandboxes={r: {"name": s["name"], "routingKey": s["routingKey"], "forkAppID": app_ids[r],
                                 "previewEndpoints": endpoint_urls(s)} for r, s in sandboxes.items()},
                  routegroup={"name": rg["name"], "routingKey": rg["routingKey"],
                              "previewEndpoints": endpoint_urls(rg)},
                  daprServices=native)
        self.wait("baseline and fork application readiness", self.all_pods)
        self.wait("application routing convergence", self.routing_converged)
        self.save(phase="ready")
        return self.status()

    def all_pods(self):
        if not self.baseline_pods():
            return None
        pods = [p for p in self.get("pods")["items"] if not p["metadata"].get("deletionTimestamp")]
        for role in ROLES:
            key = self.state["sandboxes"][role]["routingKey"]
            selected = [p for p in pods if p["metadata"].get("labels", {}).get("signadot.com/sandbox-routing-key") == key]
            if not selected or not all(pod_ready(p, ["app", "daprd"]) and
                next((c.get("image") for c in p["spec"]["containers"] if c["name"] == "app"), None) == self.state["image"]
                for p in selected):
                return None
        expected = set(APP_IDS) | set(fork_app_ids(self.args.name, self.args.namespace).values())
        return [p for p in pods if p["metadata"].get("annotations", {}).get("dapr.io/app-id") in expected]

    def routing_converged(self):
        # This hook checks the application's public state rather than assuming the
        # Signadot Ready flag implies routes.
        observations = []
        for pod in self.all_pods() or []:
            result = self.kube("exec", "-n", self.args.namespace, pod["metadata"]["name"], "-c", "app", "--", "python", "-c",
                "import json,urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/state',timeout=15).read().decode())")
            observations.append({"pod": pod["metadata"]["name"], "state": json.loads(result)})
        write_json(self.directory / "evidence" / "routing-state.json", observations)
        # One observation per baseline plus one per fork; never a lower bound
        # that a partially converged namespace could satisfy.
        return len(observations) == len(APP_IDS) + len(ROLES) and self.validate_routing(observations)

    def validate_routing(self, observations):
        keys = {role: s["routingKey"] for role, s in self.state["sandboxes"].items()}
        group = self.state["routegroup"]["routingKey"]
        app_ids = fork_app_ids(self.args.name, self.args.namespace)
        for observation in observations:
            state = observation["state"]
            if state.get("ready") is not True:
                return False
            for role in INVOCATION_ROLES:
                snapshot = state.get("routes", {}).get(ROLES[role], {})
                sandbox = sandbox_name(self.args.name, role)
                owners, ids = snapshot.get("owners") or {}, snapshot.get("appIDs") or {}
                # Check only this tutorial's keys: other sandboxes (a pull request's, an
                # agent's) may fork the same workloads at the same time.
                if (not snapshot.get("usable")
                        or any(owners.get(key) != sandbox for key in (keys[role], group))
                        or any(ids.get(key) != app_ids[role] for key in (keys[role], group))):
                    return False
        return bool(observations)

    def status(self):
        if not self.state:
            return {"name": self.args.name, "phase": "absent", "stateDir": str(self.directory)}
        ns = self.namespace()
        if not ns:
            return {**self.state, "namespacePresent": False}
        pods = self.get("pods")["items"]
        summary = [{"name": p["metadata"]["name"], "appID": p["metadata"].get("annotations", {}).get("dapr.io/app-id"),
                    "sandbox": p["metadata"].get("annotations", {}).get("signadot.com/sandbox-spec-name"),
                    "containers": [{"name": c["name"], "ready": c.get("ready", False), "restarts": c.get("restartCount", 0)}
                                   for c in p.get("status", {}).get("containerStatuses", [])]} for p in pods]
        self.save(pods=summary, namespacePresent=True)
        write_json(self.directory / "evidence" / "status.json", self.state)
        return self.state

    def down(self):
        self.check_local()
        if self.state is None:
            if self.get("namespace", self.args.namespace, False):
                raise TutorialError("Local ownership receipt missing; refusing namespace deletion")
            return {"name": self.args.name, "phase": "absent"}
        ns = self.namespace()
        # Preflight every account object before the first deletion.
        objects = [("routegroup", f"{self.args.name}-combined")] + [("sandbox", f"{self.args.name}-{r}") for r in ROLES]
        existing = [(kind, name) for kind, name in objects if self.account_object(kind, name)]
        self.save(phase="deleting")
        for kind, name in existing:
            if not self.account_object(kind, name):
                continue
            self.log(f"Deleting owned {kind} {name}")
            self.run(["signadot", kind, "delete", name, "--wait=false", "-o", "json"])
        self.wait("owned Signadot objects to disappear", lambda: all(not self.account_object(kind, name) for kind, name in objects))
        if ns:
            current = self.get("namespace", self.args.namespace, False)
            if current:
                require_owned(current, self.owner)
                self.kube("delete", "namespace", self.args.namespace, "--wait=false")
                self.wait("owned namespace and its Redis PVC to disappear", lambda: not self.get("namespace", self.args.namespace, False))
        self.save(phase="deleted", namespacePresent=False)
        return self.state


def parser():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--context", required=True,
                     help="Explicit local kubeconfig context: a Minikube profile, or docker-desktop")
    cli.add_argument("--cluster", required=True, help="Signadot cluster name for this same local installation")
    cli.add_argument("--name", default="sd-dapr-tutorial", help="Globally unique Signadot name prefix (at most 20 characters)")
    cli.add_argument("--namespace", help="Application namespace; defaults to --name")
    cli.add_argument("--image", help="Application image already loaded into the selected local cluster")
    cli.add_argument("--service-account", default="default", help="Existing namespaced service account to use")
    cli.add_argument("--timeout", type=int, default=300, help="Maximum seconds per convergence phase")
    cli.add_argument("--state-dir", type=Path, default=ROOT / ".state", help="Parent directory for ownership receipts and evidence")
    cli.add_argument("command", choices=("doctor", "up", "reconcile", "status", "down"))
    return cli


def main():
    cli = parser()
    args = cli.parse_args()
    args.namespace = args.namespace or args.name
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,18}[a-z0-9]|[a-z]", args.name):
        cli.error("--name must be a DNS label starting with a letter, at most 20 characters")
    if len(args.namespace) > 63 or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", args.namespace):
        cli.error("--namespace must be a DNS label of at most 63 characters")
    if args.timeout < 10:
        cli.error("--timeout must be at least 10 seconds")
    tutorial = None
    try:
        with state_lock(args):
            tutorial = Tutorial(args)
            try:
                result = getattr(tutorial, args.command)()
            except (TutorialError, subprocess.TimeoutExpired) as exc:
                if tutorial.state and args.command != "status":
                    tutorial.save(lastError=str(exc), failedAt=stamp())
                raise
            print(json.dumps(result, indent=2, sort_keys=True), flush=True)
            if args.command == "doctor":
                # The report above is long. Say plainly that every check passed, because
                # reaching this line at all means none of them raised. stdout is flushed
                # first so this verdict is the last line the reader sees.
                print(f"OK: doctor found no blocking problem for '{args.name}' in "
                      f"namespace '{args.namespace}'. Nothing has been created yet; run 'up' next.",
                      file=sys.stderr)
    except (TutorialError, subprocess.TimeoutExpired) as exc:
        print(f"tutorial: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
