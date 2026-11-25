"""Select a logical subscriber before interpreting its business payload.

Use only with independent broker deliveries per logical subscriber group.
A nonowner can acknowledge its copy; it must not acknowledge another group's
only copy on a competing queue. The rules callback is supplied by the
application so snapshot freshness stays explicit.
"""
from collections.abc import Callable

from signadot.routes_api import AppIDs, Rules, Workload
from signadot.routing import RoutingError


class SubscriptionGuard:
    def __init__(self, workload: Workload, *, app_id: str, sandbox: str,
                 app_ids: AppIDs, rules: Callable[[], Rules]):
        # A fork created with an app ID that breaks the naming rule would consume
        # under one identity while callers invoke another. Refuse to start rather
        # than consume under a name nobody can reach.
        expected = app_ids.target(workload, sandbox or None)
        if expected != app_id:
            raise RoutingError(f"worker app ID {app_id!r} disagrees with the naming rule, "
                               f"which expects {expected!r} for this workload and sandbox")
        self.workload = workload
        self.app_id = app_id
        self.sandbox = sandbox
        self.rules = rules

    def owns(self, key: str | None) -> bool:
        """Return ownership for a validated key, or raise if it cannot be decided.

        A key the map carries but that does not fork this workload selects
        baseline. A key the map does not carry at all is a routing error, as is
        an unavailable map, so callers retry instead of silently acknowledging
        every copy. Letting an unknown key mean baseline would let one incomplete
        snapshot hand the baseline group another group's only message. An
        unkeyed message needs no Routes API snapshot.
        """
        owner = self.rules().owner_for(key) if key is not None else ""
        # Ownership is a comparison of sandbox names. This worker never needs to know
        # another group's app ID: the owner receives its own copy in its own consumer
        # group regardless.
        return owner == self.sandbox
