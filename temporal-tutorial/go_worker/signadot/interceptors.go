package signadot

import (
	"context"
	"fmt"
	"net/url"
	"strings"
	"time"

	"go.opentelemetry.io/otel/baggage"
	commonpb "go.temporal.io/api/common/v1"
	"go.temporal.io/sdk/activity"
	"go.temporal.io/sdk/converter"
	"go.temporal.io/sdk/interceptor"
	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/workflow"
)

const (
	routingKeyBaggageKey = "sd-routing-key"
	traceHeaderKey       = "_tracer-data"
)

type tracePayloadContextKey struct{}

// SelectiveTaskInterceptor intercepts workflows and activities to enforce
// routing-key-based task selection via the RoutesAPIClient.
type SelectiveTaskInterceptor struct {
	interceptor.WorkerInterceptorBase
	routesClient *RoutesAPIClient
	workerIdent  string
}

// NewSelectiveTaskInterceptor creates an interceptor that gates task execution
// based on routing rules. Workflows delegate the routing decision to the
// "signadotShouldProcess" local activity registered by the worker.
func NewSelectiveTaskInterceptor(routesClient *RoutesAPIClient, workerIdent string) *SelectiveTaskInterceptor {
	return &SelectiveTaskInterceptor{
		routesClient: routesClient,
		workerIdent:  workerIdent,
	}
}

// InterceptWorkflow wraps the workflow inbound interceptor.
func (i *SelectiveTaskInterceptor) InterceptWorkflow(
	ctx workflow.Context,
	next interceptor.WorkflowInboundInterceptor,
) interceptor.WorkflowInboundInterceptor {
	inbound := &selectiveWorkflowInboundInterceptor{parent: i}
	inbound.Next = next
	return inbound
}

// InterceptActivity wraps the activity inbound interceptor.
func (i *SelectiveTaskInterceptor) InterceptActivity(
	ctx context.Context,
	next interceptor.ActivityInboundInterceptor,
) interceptor.ActivityInboundInterceptor {
	inbound := &selectiveActivityInboundInterceptor{parent: i}
	inbound.Next = next
	return inbound
}

type selectiveWorkflowInboundInterceptor struct {
	interceptor.WorkflowInboundInterceptorBase
	parent *SelectiveTaskInterceptor
}

func (i *selectiveWorkflowInboundInterceptor) Init(outbound interceptor.WorkflowOutboundInterceptor) error {
	wrapped := &selectiveWorkflowOutboundInterceptor{}
	wrapped.Next = outbound
	return i.Next.Init(wrapped)
}

func (i *selectiveWorkflowInboundInterceptor) ExecuteWorkflow(
	ctx workflow.Context,
	in *interceptor.ExecuteWorkflowInput,
) (interface{}, error) {
	// Extract routing key from the _tracer-data header (deterministic parse, no I/O)
	tracePayload := interceptor.WorkflowHeader(ctx)[traceHeaderKey]
	routingKey := routingKeyFromHeaders(interceptor.WorkflowHeader(ctx))
	ctx = workflow.WithValue(ctx, tracePayloadContextKey{}, tracePayload)

	// Delegate routing decision to a local activity so it's recorded in history
	// and replays are deterministic: once a worker accepts the workflow, later
	// replays see the recorded decision and proceed.
	localCtx := workflow.WithLocalActivityOptions(ctx, workflow.LocalActivityOptions{
		ScheduleToCloseTimeout: 5 * time.Second,
	})
	var shouldProcess bool
	err := workflow.ExecuteLocalActivity(
		localCtx,
		"signadotShouldProcess",
		routingKey,
	).Get(localCtx, &shouldProcess)
	if err != nil {
		// Panic, don't return: in the Go SDK an error returned from workflow
		// code fails the workflow execution permanently, while a panic fails
		// only this workflow task, which the server retries. A transient
		// routing-check failure must never kill the workflow.
		panic(fmt.Sprintf("signadot routing check failed for routing key '%s': %v", routingKey, err))
	}

	if !shouldProcess {
		panic(fmt.Sprintf(
			"Workflow/Worker cannot handle routing key: '%s' - Worker: %s",
			routingKey, i.parent.workerIdent,
		))
	}

	workflow.GetLogger(ctx).Info(
		fmt.Sprintf(
			"[Worker:%s] Workflow: %s: Processing task with routing key '%s'",
			i.parent.workerIdent, workflow.GetInfo(ctx).WorkflowType.Name, routingKey,
		),
	)

	// Propagate _tracer-data header to activities via the outbound interceptor
	return i.Next.ExecuteWorkflow(ctx, in)
}

type selectiveWorkflowOutboundInterceptor struct {
	interceptor.WorkflowOutboundInterceptorBase
}

// propagateTracerHeader copies the _tracer-data header onto the outbound call.
// The SDK gives every outbound call a fresh empty header, so without this the
// routing key would be lost on anything the workflow schedules.
func propagateTracerHeader(ctx workflow.Context) {
	if tracePayload, ok := ctx.Value(tracePayloadContextKey{}).(*commonpb.Payload); ok && tracePayload != nil {
		interceptor.WorkflowHeader(ctx)[traceHeaderKey] = tracePayload
	}
}

func (i *selectiveWorkflowOutboundInterceptor) ExecuteActivity(
	ctx workflow.Context,
	activityType string,
	args ...interface{},
) workflow.Future {
	propagateTracerHeader(ctx)
	return i.Next.ExecuteActivity(ctx, activityType, args...)
}

func (i *selectiveWorkflowOutboundInterceptor) ExecuteLocalActivity(
	ctx workflow.Context,
	activityType string,
	args ...interface{},
) workflow.Future {
	propagateTracerHeader(ctx)
	return i.Next.ExecuteLocalActivity(ctx, activityType, args...)
}

func (i *selectiveWorkflowOutboundInterceptor) ExecuteChildWorkflow(
	ctx workflow.Context,
	childWorkflowType string,
	args ...interface{},
) workflow.ChildWorkflowFuture {
	propagateTracerHeader(ctx)
	return i.Next.ExecuteChildWorkflow(ctx, childWorkflowType, args...)
}

func (i *selectiveWorkflowOutboundInterceptor) SignalExternalWorkflow(
	ctx workflow.Context,
	workflowID string,
	runID string,
	signalName string,
	arg interface{},
) workflow.Future {
	propagateTracerHeader(ctx)
	return i.Next.SignalExternalWorkflow(ctx, workflowID, runID, signalName, arg)
}

func (i *selectiveWorkflowOutboundInterceptor) SignalChildWorkflow(
	ctx workflow.Context,
	workflowID string,
	signalName string,
	arg interface{},
) workflow.Future {
	propagateTracerHeader(ctx)
	return i.Next.SignalChildWorkflow(ctx, workflowID, signalName, arg)
}

func (i *selectiveWorkflowOutboundInterceptor) NewContinueAsNewError(
	ctx workflow.Context,
	wfn interface{},
	args ...interface{},
) error {
	propagateTracerHeader(ctx)
	return i.Next.NewContinueAsNewError(ctx, wfn, args...)
}

type selectiveActivityInboundInterceptor struct {
	interceptor.ActivityInboundInterceptorBase
	parent *SelectiveTaskInterceptor
}

func (i *selectiveActivityInboundInterceptor) ExecuteActivity(
	ctx context.Context,
	in *interceptor.ExecuteActivityInput,
) (interface{}, error) {
	info := activity.GetInfo(ctx)
	activityType := info.ActivityType.Name

	// Decode the _tracer-data header once; both the routing check and the
	// baggage bridge read from it.
	carrier := carrierFromHeaders(interceptor.Header(ctx))

	// For non-local activities, check if we should process this routing key
	if !info.IsLocalActivity {
		routingKey := routingKeyFromCarrier(carrier)
		if !i.parent.routesClient.ShouldProcess(routingKey) {
			// Retryable by design: the server redelivers until the right
			// worker claims the task. NextRetryDelay keeps wrong-worker
			// bounces fast instead of following the app's backoff curve.
			return nil, temporal.NewApplicationErrorWithOptions(
				fmt.Sprintf(
					"Activity/Worker cannot handle routing key: '%s' - Worker: %s",
					routingKey, i.parent.workerIdent,
				),
				"RoutingKeyNotHandled",
				temporal.ApplicationErrorOptions{NextRetryDelay: time.Second},
			)
		}

		activity.GetLogger(ctx).Info(
			fmt.Sprintf(
				"[Worker:%s] Activity: %s: Processing task with routing key '%s'",
				i.parent.workerIdent, activityType, routingKey,
			),
		)
	}

	// Bridge OTel baggage from headers into the context so outbound HTTP calls
	// made with an OTel-instrumented client carry the sd-routing-key
	if bagStr := carrier["baggage"]; bagStr != "" {
		if b, err := baggage.Parse(bagStr); err != nil {
			// A malformed baggage header must not fail the activity: it would
			// be redelivered identically to every worker and never succeed.
			activity.GetLogger(ctx).Warn("Ignoring malformed OpenTelemetry baggage header", "err", err)
		} else {
			ctx = baggage.ContextWithBaggage(ctx, b)
			if !info.IsLocalActivity {
				activity.GetLogger(ctx).Info(
					fmt.Sprintf(
						"[Worker:%s] Activity: %s: outbound calls made with an OTel-instrumented HTTP client will carry baggage",
						i.parent.workerIdent, activityType,
					),
				)
			}
		}
	}

	return i.Next.ExecuteActivity(ctx, in)
}

// routingKeyFromHeaders extracts sd-routing-key from the _tracer-data header
// using a deterministic string parse (a pure function with no I/O, so it is
// safe in workflow code and replays identically).
func routingKeyFromHeaders(headers map[string]*commonpb.Payload) string {
	return routingKeyFromCarrier(carrierFromHeaders(headers))
}

// routingKeyFromCarrier extracts sd-routing-key from a decoded carrier map.
func routingKeyFromCarrier(carrier map[string]string) string {
	baggage := carrier["baggage"]
	if baggage == "" {
		return ""
	}

	// Entries look like `key=value` optionally followed by `;properties`
	for _, entry := range strings.Split(baggage, ",") {
		entry = strings.TrimSpace(entry)
		parts := strings.Split(entry, ";")
		pair := parts[0]

		eq := strings.Index(pair, "=")
		if eq < 0 {
			continue
		}

		key := strings.TrimSpace(pair[:eq])
		if key == routingKeyBaggageKey {
			val := strings.TrimSpace(pair[eq+1:])
			// Percent-decode the value. PathUnescape (unlike QueryUnescape)
			// leaves literal '+' intact, which W3C baggage values may contain.
			unescaped, err := url.PathUnescape(val)
			if err != nil {
				return val
			}
			return unescaped
		}
	}

	return ""
}

func carrierFromHeaders(headers map[string]*commonpb.Payload) map[string]string {
	payload := headers[traceHeaderKey]
	if payload == nil {
		return nil
	}

	var carrier map[string]string
	if err := converter.GetDefaultDataConverter().FromPayload(payload, &carrier); err != nil {
		return nil
	}
	return carrier
}
