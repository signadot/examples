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
	routesClient  *RoutesAPIClient
	sandboxName   string
	taskQueue     string
	workerIdent   string
	shouldProcess func(ctx context.Context, routingKey string) (bool, error)
}

// NewSelectiveTaskInterceptor creates an interceptor that gates task execution
// based on routing rules. shouldProcessFunc is a local activity that consults
// the routes cache (used by workflows, which cannot do I/O directly).
func NewSelectiveTaskInterceptor(
	routesClient *RoutesAPIClient,
	sandboxName string,
	taskQueue string,
	shouldProcessFunc func(ctx context.Context, routingKey string) (bool, error),
) *SelectiveTaskInterceptor {
	ident := fmt.Sprintf("sandbox=%s task_queue=%s", sandboxName, taskQueue)
	if sandboxName == "" {
		ident = fmt.Sprintf("sandbox=baseline task_queue=%s", taskQueue)
	}
	return &SelectiveTaskInterceptor{
		routesClient:  routesClient,
		sandboxName:   sandboxName,
		taskQueue:     taskQueue,
		workerIdent:   ident,
		shouldProcess: shouldProcessFunc,
	}
}

// ENG-REVIEW: verify interceptor method signatures match Temporal Go SDK ChainedInterceptor API
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
		return nil, fmt.Errorf("signadot routing check failed for routing key '%s': %w", routingKey, err)
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

func (i *selectiveWorkflowOutboundInterceptor) ExecuteActivity(
	ctx workflow.Context,
	activityType string,
	args ...interface{},
) workflow.Future {
	if tracePayload, ok := ctx.Value(tracePayloadContextKey{}).(*commonpb.Payload); ok && tracePayload != nil {
		interceptor.WorkflowHeader(ctx)[traceHeaderKey] = tracePayload
	}
	return i.Next.ExecuteActivity(ctx, activityType, args...)
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

	// For non-local activities, check if we should process this routing key
	if !info.IsLocalActivity {
		routingKey := routingKeyFromHeaders(interceptor.Header(ctx))
		if !i.parent.routesClient.ShouldProcess(routingKey) {
			return nil, fmt.Errorf(
				"Activity/Worker cannot handle routing key: '%s' - Worker: %s",
				routingKey, i.parent.workerIdent,
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
	// from the activity carry the sd-routing-key
	bagStr := extractBaggageFromHeaders(interceptor.Header(ctx))
	if bagStr != "" {
		// ENG-REVIEW: verify baggage.NewMember and baggage.New API signatures
		b, err := baggage.Parse(bagStr)
		if err != nil {
			return nil, fmt.Errorf("parse OpenTelemetry baggage: %w", err)
		}
		ctx = baggage.ContextWithBaggage(ctx, b)

		if !info.IsLocalActivity {
			activity.GetLogger(ctx).Info(
				fmt.Sprintf(
					"[Worker:%s] Activity: %s: outbound HTTP calls will carry baggage",
					i.parent.workerIdent, activityType,
				),
			)
		}
	}

	return i.Next.ExecuteActivity(ctx, in)
}

// ENG-REVIEW: verify header type - may be map[string][]byte or different structure
// routingKeyFromHeaders extracts sd-routing-key from the _tracer-data header
// using a deterministic string parse (no OTel SDK calls, so it works in the
// workflow isolate and replays identically).
func routingKeyFromHeaders(headers map[string]*commonpb.Payload) string {
	if len(headers) == 0 {
		return ""
	}

	carrier := carrierFromHeaders(headers)

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
			// Unescape the value
			unescaped, _ := url.QueryUnescape(val)
			return unescaped
		}
	}

	return ""
}

// extractBaggageFromHeaders pulls the baggage string from _tracer-data for OTel context restoration
func extractBaggageFromHeaders(headers map[string]*commonpb.Payload) string {
	carrier := carrierFromHeaders(headers)
	return carrier["baggage"]
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
