/**
 * Application worker entry point. All Signadot-specific concerns (routing
 * interceptors, routeserver polling, OTel propagation) live in the
 * platform-owned SandboxAwareWorker -- application code only registers its
 * workflows and activities.
 */
import { SandboxAwareWorker } from './signadot/worker';
import * as activities from './activities';

async function main(): Promise<void> {
  const taskQueue = process.env.TASK_QUEUE;
  if (!taskQueue) {
    throw new Error('Missing required environment variable: TASK_QUEUE');
  }

  const worker = await SandboxAwareWorker.create({
    taskQueue,
    workflowsPath: require.resolve('./workflows'),
    activities,
  });

  console.log('Starting to poll for tasks...');
  await worker.run();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
