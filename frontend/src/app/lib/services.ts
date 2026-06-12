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
import { apiClient } from './api';

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
  return listJobsSdk({
    client: apiClient,
    query: {
      status: params?.status ?? null,
      type: params?.type ?? null,
      priority: params?.priority ?? null,
      offset: params?.offset ?? 0,
      limit: params?.limit ?? 200,
    },
  });
}

export function createJob(data: JobCreate) {
  return createJobSdk({
    client: apiClient,
    body: data,
  });
}

export function fetchJob(jobId: string) {
  return getJobSdk({
    client: apiClient,
    path: { job_id: jobId },
  });
}

export function cancelJob(jobId: string) {
  return cancelJobSdk({
    client: apiClient,
    path: { job_id: jobId },
  });
}

export function fetchJobLogs(jobId: string) {
  return getJobLogsSdk({
    client: apiClient,
    path: { job_id: jobId },
  });
}

/* ------------------------------------------------------------------ */
/* Dashboard                                                           */
/* ------------------------------------------------------------------ */

export function fetchDashboardStats() {
  return dashboardStatsSdk({ client: apiClient });
}

/* ------------------------------------------------------------------ */
/* Dead-Letter Queue                                                   */
/* ------------------------------------------------------------------ */

export function fetchDlqJobs() {
  return listDlqJobsSdk({ client: apiClient });
}

export function retryDlqJob(jobId: string) {
  return retryDlqJobSdk({
    client: apiClient,
    path: { job_id: jobId },
  });
}

/* ------------------------------------------------------------------ */
/* Worker Fleet                                                        */
/* ------------------------------------------------------------------ */

export function fetchWorkerFleet() {
  return getWorkerFleetSdk({ client: apiClient });
}

/* ------------------------------------------------------------------ */
/* Scheduler Info                                                       */
/* ------------------------------------------------------------------ */

export function fetchSchedulerInfo() {
  return getSchedulerInfoSdk({ client: apiClient });
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
