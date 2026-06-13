import { useState, useEffect, useCallback } from 'react';
import { useWebSocket } from './websocket';
import {
  fetchJobs,
  fetchDashboardStats,
  fetchDlqJobs,
  createJob,
  cancelJob,
  retryDlqJob,
  fetchWorkerFleet,
  fetchSchedulerInfo,
} from './services';
import type { JobResponse, JobCreate, DashboardStats, WorkerFleetStatus, WorkerState, SchedulerInfo } from './services';

/* ------------------------------------------------------------------ */
/* Jobs hook — polled list with WS-driven splicing                    */
/* ------------------------------------------------------------------ */

export function useJobs(initialFilter?: { status?: string }) {
  const [jobs, setJobs] = useState<JobResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [limit] = useState(25);
  const { lastMessage } = useWebSocket();

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchJobs({ status: initialFilter?.status, offset: page * limit, limit });
      setJobs(data.jobs);
      setTotal(data.total);
    } catch { /* toast shown by interceptor */ }
    setLoading(false);
  }, [initialFilter?.status, page, limit]);

  // Initial fetch + re-fetch when page/filter changes
  useEffect(() => {
    refresh();
  }, [refresh]);

  // Re-fetch the current page on any WS event so the table stays live
  useEffect(() => {
    if (lastMessage) refresh();
  }, [lastMessage, refresh]);

  return { jobs, loading, total, page, limit, refresh, setPage };
}

/* ------------------------------------------------------------------ */
/* Dashboard stats hook                                                */
/* ------------------------------------------------------------------ */

export function useStats() {
  const [stats, setStats] = useState<DashboardStats>({ pending: 0, processing: 0, completed: 0, failed: 0, cancelled: 0, total: 0 });
  const { lastMessage } = useWebSocket();

  const refresh = useCallback(async () => {
    try {
      const data = await fetchDashboardStats();
      setStats(data);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  // Refresh stats on any WS event
  useEffect(() => {
    if (lastMessage) refresh();
  }, [lastMessage, refresh]);

  return { stats, refresh };
}

/* ------------------------------------------------------------------ */
/* DLQ hook                                                             */
/* ------------------------------------------------------------------ */

export function useDlq() {
  const [dlqJobs, setDlqJobs] = useState<JobResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const { lastMessage } = useWebSocket();

  const refresh = useCallback(async () => {
    try {
      const data = await fetchDlqJobs();
      setDlqJobs(data);
    } catch { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  // Refresh whenever a job fails or is retried from DLQ
  useEffect(() => {
    if (lastMessage) refresh();
  }, [lastMessage, refresh]);

  return { dlqJobs, loading, refresh };
}

/* ------------------------------------------------------------------ */
/* Mutation helpers                                                     */
/* ------------------------------------------------------------------ */

export function useCreateJob() {
  const [loading, setLoading] = useState(false);

  const submit = async (data: JobCreate) => {
    setLoading(true);
    try {
      return await createJob(data);
    } finally {
      setLoading(false);
    }
  };

  return { submit, loading };
}

export function useCancelJob() {
  return async (jobId: string) => {
    try { await cancelJob(jobId); } catch { /* toasted */ }
  };
}

export function useRetryDlqJob() {
  return async (jobId: string) => {
    try { await retryDlqJob(jobId); } catch { /* toasted */ }
  };
}

/* ------------------------------------------------------------------ */
/* Worker fleet hook                                                   */
/* ------------------------------------------------------------------ */

export function useWorkerFleet() {
  const [fleet, setFleet] = useState<WorkerFleetStatus>({ workers: [], total_workers: 0, busy_workers: 0 });
  const { lastMessage } = useWebSocket();

  const refresh = useCallback(async () => {
    try {
      const data = await fetchWorkerFleet();
      setFleet(data);
    } catch { /* worker process may be down */ }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  // Refresh on any WS event (job state changes may update worker assignments)
  useEffect(() => {
    if (lastMessage) refresh();
  }, [lastMessage, refresh]);

  return { fleet, refresh };
}

/* ------------------------------------------------------------------ */
/* Scheduler info hook                                                  */
/* ------------------------------------------------------------------ */

export function useSchedulerInfo() {
  const [info, setInfo] = useState<SchedulerInfo | null>(null);

  useEffect(() => {
    fetchSchedulerInfo()
      .then((data) => setInfo(data))
      .catch(() => { });
  }, []);

  return info;
}
