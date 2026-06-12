import type { JobResponse } from '../../sdk/types.gen';

/* ------------------------------------------------------------------ */
/* UI-level job type (extends API response with computed fields)       */
/* ------------------------------------------------------------------ */

export type JobStatus =
  | 'pending'
  | 'processing'
  | 'completed'
  | 'failed'
  | 'cancelled';

export type JobType = 'send_email' | 'webhook_delivery' | 'log_processing';

export type Priority = 1 | 2 | 3;

export type RecurringInterval =
  | 'every_1_minute'
  | 'every_5_minutes'
  | 'every_1_hour';

/** A Job is just the API response plus any UI-level derivations. */
export type Job = JobResponse;

/* ------------------------------------------------------------------ */
/* UI-level log entry                                                  */
/* ------------------------------------------------------------------ */

export interface LogEntry {
  id: string;
  jobId: string;
  event: string;
  level: LogLevel;
  message: string;
  timestamp: number;
}

export type LogLevel = 'info' | 'warn' | 'error' | 'success';

/* ------------------------------------------------------------------ */
/* Constants                                                          */
/* ------------------------------------------------------------------ */

export const JOB_TYPE_LABEL: Record<string, string> = {
  send_email: 'Email Delivery',
  webhook_delivery: 'Webhook Delivery',
  log_processing: 'Log Processing',
} as const;

export const PRIORITY_LABEL: Record<number, string> = {
  1: 'High',
  2: 'Medium',
  3: 'Low',
} as const;

export const INTERVAL_LABEL: Record<string, string> = {
  every_1_minute: 'Every 1 min',
  every_5_minutes: 'Every 5 min',
  every_1_hour: 'Every 1 hour',
} as const;

export const STATUS_LABEL: Record<string, string> = {
  pending: 'Pending',
  processing: 'Processing',
  completed: 'Completed',
  failed: 'Failed',
  cancelled: 'Cancelled',
};

/* ------------------------------------------------------------------ */
/* Starvation / aging constants                                       */
/* ------------------------------------------------------------------ */

/**
 * Aging window: a job waiting 1 hour past its scheduled time gains
 * a full priority tier improvement. Matches the backend heap formula:
 *   V = base_priority + (1.0 / 3600.0) × scheduled_at_timestamp
 *
 * The timing wheel engine has no aging — only the heap uses this.
 */
export const AGING_WINDOW_MS = 3_600_000; // 1 hour

/** Max retries before a job lands in the DLQ. */
export const MAX_RETRIES = 3;
