/**
 * Payload models. Field names are snake_case to stay wire-compatible with the
 * Python client and worker (Python dataclasses serialize with snake_case
 * keys), so the same workflow can be started from either SDK.
 */

export interface PaymentDetails {
  from_account: string;
  to_account: string;
  amount: string;
  currency?: string;
  reference: string;
}

export interface WithdrawRequest {
  account_id: string;
  amount: string;
  reference: string;
}

export interface WithdrawResponse {
  transaction_id: string;
  account_id: string;
  amount: string;
  balance_after: string;
  success: boolean;
  message: string;
}

export interface DepositRequest {
  account_id: string;
  amount: string;
  reference: string;
}

export interface DepositResponse {
  transaction_id: string;
  account_id: string;
  amount: string;
  balance_after: string;
  success: boolean;
  message: string;
}
