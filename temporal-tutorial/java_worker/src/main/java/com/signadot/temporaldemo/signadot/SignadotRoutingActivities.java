package com.signadot.temporaldemo.signadot;

import io.temporal.activity.ActivityInterface;
import io.temporal.activity.ActivityMethod;

/**
 * Platform-provided local activity used by the workflow routing check.
 * Workflows cannot do I/O or read mutable process state, so the routing
 * decision runs as a local activity: its result is recorded in workflow
 * history, which keeps replays deterministic. Same pattern as the Go and
 * TypeScript workers ("signadotShouldProcess").
 */
@ActivityInterface
public interface SignadotRoutingActivities {
    @ActivityMethod(name = "signadotShouldProcess")
    boolean shouldProcess(String routingKey);
}
