"""The naming rule that gives every sandbox fork its own Dapr app ID.

A fork needs an app ID of its own, because Dapr keeps one `<app-id>-dapr` Service per
app ID. Nothing in the Routes API carries that app ID: a routing rule names the
destination sandbox and nothing else. So both sides apply the same pure function to
the sandbox name and the forked workload:

* whatever creates the sandbox (a person, a CI job, an agent) computes the app ID and
  writes it into the fork's `dapr.io/app-id` annotation;
* a caller that learns from the Routes API which sandbox owns a routing key computes
  the same app ID and invokes it.

Neither side needs a registry, and a sandbox created after a caller started is
reachable as soon as the Routes API carries its key.

Standard library only, so a CI job can run this file directly, without the rest of
the package:

    python3 appid.py --sandbox pr-123-checkout --namespace shop --name checkout
"""
import argparse
import hashlib
import re

# Reserved for forks. No baseline app ID may start with it, so a computed fork ID can
# never land on a real baseline service.
FORK_PREFIX = "sbx-"
# Dapr names its Service `<app-id>-dapr`, and a Service name is a DNS label of at
# most 63 characters, which leaves 58 for the app ID.
MAX_APP_ID_LENGTH = 58
_DIGEST_LENGTH = 8
_APP_ID = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,56}[a-z0-9])?")


def valid_app_id(value):
    """True for a Kubernetes-mode Dapr app ID: a DNS label of at most 58 characters."""
    return isinstance(value, str) and _APP_ID.fullmatch(value) is not None


def is_fork_app_id(value):
    return isinstance(value, str) and value.startswith(FORK_PREFIX)


def fork_app_id(sandbox, kind, namespace, name):
    """The Dapr app ID that `sandbox` runs its fork of workload kind/namespace/name under.

    The readable part is `<sandbox>-<workload>`, truncated to fit. The digest covers
    the full, untruncated identity, so two forks never share an ID even when their
    readable parts truncate or hyphenate to the same text ("a-b" + "c" and
    "a" + "b-c" both read "a-b-c").
    """
    for label, value in (("sandbox", sandbox), ("kind", kind), ("namespace", namespace), ("name", name)):
        if not isinstance(value, str) or not value.strip() or "/" in value:
            raise ValueError(f"{label} must be a nonempty name without '/'")
    digest = hashlib.sha256("/".join((kind, namespace, name, sandbox)).encode()).hexdigest()[:_DIGEST_LENGTH]
    readable = re.sub(r"[^a-z0-9]+", "-", f"{sandbox}-{name}".lower()).strip("-")
    room = MAX_APP_ID_LENGTH - len(FORK_PREFIX) - len(digest) - 1
    readable = readable[:room].rstrip("-")
    return f"{FORK_PREFIX}{readable}-{digest}" if readable else f"{FORK_PREFIX}{digest}"


def main():
    cli = argparse.ArgumentParser(description="Print the Dapr app ID a sandbox fork must run under.")
    cli.add_argument("--sandbox", required=True, help="Signadot sandbox name")
    cli.add_argument("--namespace", required=True, help="Namespace of the forked baseline workload")
    cli.add_argument("--name", required=True, help="Name of the forked baseline workload")
    cli.add_argument("--kind", default="Deployment", help="Kind of the forked baseline workload")
    args = cli.parse_args()
    print(fork_app_id(args.sandbox, args.kind, args.namespace, args.name))


if __name__ == "__main__":
    main()
