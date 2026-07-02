/**
 * Application activities: pure business logic. Signadot routing and
 * OpenTelemetry context propagation are handled entirely by the platform
 * layer (see src/signadot): outbound HTTP calls made from these activities
 * with an instrumented client automatically carry the sd-routing-key baggage.
 * (For a client without instrumentation, pass
 * `outboundHttpHeaders()` from '../signadot/otel' as request headers.)
 */
import { ApplicationFailure } from '@temporalio/common';
import { randomUUID } from 'crypto';
import type { WithdrawRequest, WithdrawResponse, DepositRequest, DepositResponse } from './models';

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const MOCK_BALANCES: Record<string, number> = {
  acc_001: 1000.0,
  acc_002: 500.0,
  acc_003: 2500.0,
  acc_004: 750.0,
};

async function getAccountBalance(accountId: string): Promise<number> {
  await sleep(100); // simulate database query delay
  return MOCK_BALANCES[accountId] ?? 1000.0;
}

async function updateAccountBalance(accountId: string, newBalance: number): Promise<void> {
  console.log(`Updated balance for ${accountId}: ${newBalance}`);
  await sleep(100); // simulate database update delay
}

export async function withdraw(request: WithdrawRequest): Promise<WithdrawResponse> {
  console.log(`Processing withdrawal: ${request.account_id}, amount: ${request.amount}`);
  const currentBalance = await getAccountBalance(request.account_id);
  const amount = Number(request.amount);

  // Business logic failure - Temporal won't retry this
  if (currentBalance < amount) {
    throw ApplicationFailure.nonRetryable(
      `Insufficient funds: balance=${currentBalance}, requested=${request.amount}`
    );
  }

  await sleep(500); // simulate withdrawal processing time
  const transactionId = randomUUID();
  const newBalance = currentBalance - amount;
  await updateAccountBalance(request.account_id, newBalance);

  console.log(`Withdrawal successful: ${transactionId}`);
  return {
    transaction_id: transactionId,
    account_id: request.account_id,
    amount: request.amount,
    balance_after: String(newBalance),
    success: true,
    message: 'Withdrawal successful',
  };
}

export async function deposit(request: DepositRequest): Promise<DepositResponse> {
  console.log(`Processing deposit: ${request.account_id}, amount: ${request.amount}`);
  const currentBalance = await getAccountBalance(request.account_id);
  const amount = Number(request.amount);

  await sleep(300); // simulate deposit processing time
  const transactionId = randomUUID();
  const newBalance = currentBalance + amount;
  await updateAccountBalance(request.account_id, newBalance);

  console.log(`Deposit successful: ${transactionId}`);
  return {
    transaction_id: transactionId,
    account_id: request.account_id,
    amount: request.amount,
    balance_after: String(newBalance),
    success: true,
    message: 'Deposit successful',
  };
}
