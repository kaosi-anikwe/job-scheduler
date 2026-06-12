import {
  listJobsApiV1JobsGet,
  createJobApiV1JobsPost,
  getJobApiV1JobsJobIdGet,
  cancelJobApiV1JobsJobIdCancelPatch,
  getJobLogsApiV1JobsJobIdLogsGet,
  dashboardStatsApiV1JobsDashboardStatsGet,
  listDlqJobsApiV1DlqGet,
  retryDlqJobApiV1DlqJobIdRetryPost,
} from '../../sdk/sdk.gen';
import type {
  JobResponse,
  JobCreate,
  DashboardStats,
  JobListResponse,
  ExecutionLogResponse,
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
  return listJobsApiV1JobsGet({
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
  return createJobApiV1JobsPost({
    client: apiClient,
    body: data,
  });
}

export function fetchJob(jobId: string) {
  return getJobApiV1JobsJobIdGet({
    client: apiClient,
    path: { job_id: jobId },
  });
}

export function cancelJob(jobId: string) {
  return cancelJobApiV1JobsJobIdCancelPatch({
    client: apiClient,
    path: { job_id: jobId },
  });
}

export function fetchJobLogs(jobId: string) {
  return getJobLogsApiV1JobsJobIdLogsGet({
    client: apiClient,
    path: { job_id: jobId },
  });
}

/* ------------------------------------------------------------------ */
/* Dashboard                                                           */
/* ------------------------------------------------------------------ */

export function fetchDashboardStats() {
  return dashboardStatsApiV1JobsDashboardStatsGet({ client: apiClient });
}

/* ------------------------------------------------------------------ */
/* Dead-Letter Queue                                                   */
/* ------------------------------------------------------------------ */

export function fetchDlqJobs() {
  return listDlqJobsApiV1DlqGet({ client: apiClient });
}

export function retryDlqJob(jobId: string) {
  return retryDlqJobApiV1DlqJobIdRetryPost({
    client: apiClient,
    path: { job_id: jobId },
  });
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
} from '../../sdk/types.gen';
