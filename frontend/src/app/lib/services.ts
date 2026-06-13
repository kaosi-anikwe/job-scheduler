import {
  listJobs as listJobsSdk,
  createJob as createJobSdk,
  getJob as getJobSdk,
  cancelJob as cancelJobSdk,
  getJobLogs as getJobLogsSdk,
  dashboardStats as dashboardStatsSdk,
  listDlqJobs as listDlqJobsSdk,
  retryDlqJob as retryDlqJobSdk,
  getWorkerFleet as getWorkerFleetSdk,
  getSchedulerInfo as getSchedulerInfoSdk,
} from '../../sdk/sdk.gen';
import type {
  JobCreate,
} from '../../sdk/types.gen';
import { apiClient, unwrap } from './api';

/* ------------------------------------------------------------------ */
/* Jobs                                                                */
/* ------------------------------------------------------------------ */

export function fetchJobs(params?: {
  status?: string;
  type?: string;
  priority?: number;
  offset?: number;
  limit?: number;
}) {
  return unwrap(listJobsSdk({
    client: apiClient,
    query: {
      status: params?.status ?? null,
      type: params?.type ?? null,
      priority: params?.priority ?? null,
      offset: params?.offset ?? 0,
      limit: params?.limit ?? 200,
    },
  }));
}

export function createJob(data: JobCreate) {
  return unwrap(createJobSdk({
    client: apiClient,
    body: data,
  }));
}

export function fetchJob(jobId: string) {
  return unwrap(getJobSdk({
    client: apiClient,
    path: { job_id: jobId },
  }));
}

export function cancelJob(jobId: string) {
  return unwrap(cancelJobSdk({
    client: apiClient,
    path: { job_id: jobId },
  }));
}

export function fetchJobLogs(jobId: string) {
  return unwrap(getJobLogsSdk({
    client: apiClient,
    path: { job_id: jobId },
  }));
}

/* ------------------------------------------------------------------ */
/* Dashboard                                                           */
/* ------------------------------------------------------------------ */

export function fetchDashboardStats() {
  return unwrap(dashboardStatsSdk({ client: apiClient }));
}

/* ------------------------------------------------------------------ */
/* Dead-Letter Queue                                                   */
/* ------------------------------------------------------------------ */

export function fetchDlqJobs() {
  return unwrap(listDlqJobsSdk({ client: apiClient }));
}

export function retryDlqJob(jobId: string) {
  return unwrap(retryDlqJobSdk({
    client: apiClient,
    path: { job_id: jobId },
  }));
}

/* ------------------------------------------------------------------ */
/* Worker Fleet                                                        */
/* ------------------------------------------------------------------ */

export function fetchWorkerFleet() {
  return unwrap(getWorkerFleetSdk({ client: apiClient }));
}

/* ------------------------------------------------------------------ */
/* Scheduler Info                                                       */
/* ------------------------------------------------------------------ */

export function fetchSchedulerInfo() {
  return unwrap(getSchedulerInfoSdk({ client: apiClient }));
}

/* ------------------------------------------------------------------ */
/* Re-exports for convenience                                          */
/* ------------------------------------------------------------------ */

export type {
  JobResponse,
  JobCreate,
  DashboardStats,
  JobListResponse,
  ExecutionLogResponse,
  WorkerState,
  WorkerFleetStatus,
  SchedulerInfo,
} from '../../sdk/types.gen';
