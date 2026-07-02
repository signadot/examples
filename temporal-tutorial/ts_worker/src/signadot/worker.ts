/**
 * A Temporal worker (TypeScript SDK) that automatically handles Signadot
 * sandbox routing and OpenTelemetry context propagation. TypeScript
 * counterpart of the Python `signadot` package.
 *
 * Platform-owned. Application developers pass their workflows module and
 * activity implementations; everything Signadot-specific (routeserver
 * polling, routing interceptors, the `signadotShouldProcess` local activity
 * backing the workflow-level check, and OTel context bridging) is wired up
 * here. Application workflows and activities need no Signadot- or
 * OpenTelemetry-specific code.
 */
import { Worker, NativeConnection } from '@temporalio/worker';
import { setupOpenTelemetry } from './otel';
import { RoutesAPIClient } from './routing';
import { SignadotActivityInboundInterceptor } from './activity-interceptor';

export interface SandboxAwareWorkerOptions {
  taskQueue: string;
  /** Path to the module exporting the workflows, e.g. require.resolve('./workflows') */
  workflowsPath: string;
  /** Application activity implementations (plain object of functions). */
  activities: object;
}

export class SandboxAwareWorker {
  private constructor(
    private readonly worker: Worker,
    private readonly routesClient: RoutesAPIClient,
    readonly workerIdent: string
  ) {}

  static async create(options: SandboxAwareWorkerOptions): Promise<SandboxAwareWorker> {
    setupOpenTelemetry();

    const sandboxName = process.env.SIGNADOT_SANDBOX_NAME ?? '';
    const temporalServerUrl = requireEnv('TEMPORAL_SERVER_URL');
    const refreshInterval = Number(process.env.ROUTES_API_REFRESH_INTERVAL_SECONDS ?? '120');
    const workerIdent = `sandbox=${sandboxName || 'baseline'} task_queue=${options.taskQueue}`;

    // Routes cache used by both the activity interceptor (Node.js side) and
    // the signadotShouldProcess local activity backing the workflow-level
    // routing check inside the V8 isolate.
    const routesClient = new RoutesAPIClient(sandboxName);
    await routesClient.startPolling(refreshInterval);

    const connection = await NativeConnection.connect({ address: temporalServerUrl });
    console.log(`Connected to Temporal server: ${temporalServerUrl}`);

    // Platform-provided local activity used by the workflow routing check.
    // Merged in last so applications cannot accidentally shadow it.
    const signadotShouldProcess = async (routingKey: string): Promise<boolean> => {
      const should = routesClient.shouldProcess(routingKey);
      console.log(`[Worker:${workerIdent}] signadotShouldProcess('${routingKey}') -> ${should}`);
      return should;
    };

    const worker = await Worker.create({
      connection,
      taskQueue: options.taskQueue,
      workflowsPath: options.workflowsPath,
      activities: { ...options.activities, signadotShouldProcess },
      identity: `${workerIdent} pid=${process.pid}`,
      interceptors: {
        // Runs inside the workflow V8 isolate: routing check + deterministic
        // propagation of the `_tracer-data` header to scheduled activities
        workflowModules: [require.resolve('./workflow-interceptors')],
        // Runs on the Node.js side: routing check + OTel context bridging so
        // outbound HTTP calls from activities carry sd-routing-key baggage
        activity: [(ctx) => ({ inbound: new SignadotActivityInboundInterceptor(ctx, routesClient, workerIdent) })],
      },
    });

    console.log(`Worker created successfully: ${workerIdent}`);
    return new SandboxAwareWorker(worker, routesClient, workerIdent);
  }

  /** Run the worker until shutdown; stops routeserver polling on exit. */
  async run(): Promise<void> {
    try {
      await this.worker.run();
    } finally {
      this.routesClient.stopPolling();
    }
  }

  shutdown(): void {
    this.worker.shutdown();
  }
}

function requireEnv(name: string): string {
  const value = process.env[name];
  if (value === undefined || value === '') {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}
