// Application workflows: pure business logic. Signadot routing is handled by
// platform-owned interceptors (see src/signadot) wired up by SandboxAwareWorker.
import { proxyActivities, log } from '@temporalio/workflow';
import type * as activities from './activities';
import type { PaymentDetails } from './models';

// Common retry policy for banking activities
const { withdraw, deposit } = proxyActivities<typeof activities>({
  startToCloseTimeout: '30 seconds',
  retry: {
    initialInterval: '5 seconds',
    maximumAttempts: 10,
    backoffCoefficient: 2.0,
    maximumInterval: '10 seconds',
  },
});

/** Baseline money transfer workflow - 2 step process */
export async function MoneyTransferWorkflow(paymentDetails: PaymentDetails): Promise<string> {
  log.info(
    `Starting money transfer: ${paymentDetails.from_account} -> ${paymentDetails.to_account}, amount: ${paymentDetails.amount}`
  );

  // Step 1: Withdraw money from source account
  const withdrawResult = await withdraw({
    account_id: paymentDetails.from_account,
    amount: paymentDetails.amount,
    reference: paymentDetails.reference,
  });
  log.info(`Withdrawal successful: ${withdrawResult.transaction_id}`);

  // Step 2: Deposit money to destination account
  const depositResult = await deposit({
    account_id: paymentDetails.to_account,
    amount: paymentDetails.amount,
    reference: paymentDetails.reference,
  });
  log.info(`Deposit successful: ${depositResult.transaction_id}`);

  log.info('Money transfer completed successfully');
  return `Transfer complete: ${withdrawResult.transaction_id} -> ${depositResult.transaction_id}`;
}
