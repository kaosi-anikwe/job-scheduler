import { useState } from 'react';
import { Lock, Copy, X, ChevronLeft, ChevronRight } from 'lucide-react';
import { useCancelJob } from '../lib/hooks';
import type { JobResponse } from '../lib/services';
import {
  JOB_TYPE_LABEL,
  PRIORITY_LABEL,
  INTERVAL_LABEL,
} from '../lib/types';
import {
  statusBadgeClass,
  priorityTextClass,
  timeAgo,
  inFuture,
  shortId,
  effectivePriority,
} from '../lib/format';

export function JobsTable({
  jobs,
  loading,
  total = 0,
  page = 0,
  limit = 25,
  onPageChange,
}: {
  jobs: JobResponse[];
  loading: boolean;
  total?: number;
  page?: number;
  limit?: number;
  onPageChange?: (page: number) => void;
}) {
  const [filter, setFilter] = useState<string>('all');
  const cancelJob = useCancelJob();
  const now = Date.now();

  const filtered = jobs
    .filter((j) => (filter === 'all' ? true : j.status === filter))
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

  const completedIds = new Set(
    jobs.filter((j) => j.status === 'completed').map((j) => j.id),
  );

  return (
    <div className="card bg-base-200 border border-base-300 shadow-xl">
      <div className="card-body p-4 gap-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h2 className="card-title font-display">Jobs</h2>
          <div className="join">
            {['all', 'pending', 'processing', 'completed', 'failed', 'cancelled'].map((s) => (
              <button
                key={s}
                className={`btn btn-xs join-item capitalize ${filter === s ? 'btn-primary' : 'btn-ghost'}`}
                onClick={() => setFilter(s)}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        {/* Pagination controls */}
        {total > limit && (
          <div className="flex items-center justify-between pt-2 border-t border-base-300">
            <span className="text-xs text-base-content/50">
              {total} total · page {page + 1} of {Math.ceil(total / limit)}
            </span>
            <div className="join">
              <button
                className="btn btn-xs join-item btn-ghost"
                disabled={page === 0}
                onClick={() => onPageChange?.(page - 1)}
              >
                <ChevronLeft size={14} />
              </button>
              {Array.from({ length: Math.ceil(total / limit) }, (_, i) => (
                <button
                  key={i}
                  className={`btn btn-xs join-item ${i === page ? 'btn-active' : 'btn-ghost'}`}
                  onClick={() => onPageChange?.(i)}
                >
                  {i + 1}
                </button>
              )).slice(0, 7)}
              <button
                className="btn btn-xs join-item btn-ghost"
                disabled={(page + 1) * limit >= total}
                onClick={() => onPageChange?.(page + 1)}
              >
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}

        <div className="overflow-x-auto">
          <table className="table table-zebra table-sm">
            <thead>
              <tr>
                <th>Job ID</th>
                <th>Type</th>
                <th>Priority</th>
                <th>Status</th>
                <th>Retries</th>
                <th>Scheduled</th>
                <th>Interval</th>
                <th>Created</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((job) => (
                <Row
                  key={job.id}
                  job={job}
                  now={now}
                  completedIds={completedIds}
                  onCancel={cancelJob}
                />
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={9} className="text-center text-base-content/50 py-8">
                    {loading ? 'Loading…' : 'No jobs in this view.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function Row({
  job,
  now,
  completedIds,
  onCancel,
}: {
  job: JobResponse;
  now: number;
  completedIds: Set<string>;
  onCancel: (id: string) => Promise<unknown>;
}) {
  const eff = ['pending', 'processing'].includes(job.status) ? effectivePriority(job) : job.priority;
  const aged = eff < job.priority;
  // Check if any dependency is not yet completed
  const dependencyIds: string[] = []; // API doesn't expose dependsOn in response — handled server-side
  const blockedDep = job.status === 'pending' ? dependencyIds.find((d) => !completedIds.has(d)) : undefined;
  const cancellable = job.status === 'pending' || job.status === 'processing';
  const isFailed = job.status === 'failed' && job.retry_count >= job.max_retries;

  return (
    <tr className={isFailed ? 'bg-error/5' : undefined}>
      <td>
        <button
          className="badge badge-ghost font-mono text-xs"
          title="Click to copy full id"
          onClick={() => navigator.clipboard?.writeText(job.id)}
        >
          {shortId(job.id)} <Copy size={11} className="ml-1 opacity-60" />
        </button>
      </td>
      <td className="whitespace-nowrap">{JOB_TYPE_LABEL[job.type] ?? job.type}</td>
      <td>
        <span className={`font-bold ${priorityTextClass(job.priority)}`}>
          {PRIORITY_LABEL[job.priority] ?? job.priority}
        </span>
        {aged && (
          <span
            className="badge badge-xs badge-info badge-outline ml-1 align-middle"
            title="Effective priority raised by starvation aging"
          >
            ↑ aged → {PRIORITY_LABEL[eff] ?? eff}
          </span>
        )}
      </td>
      <td>
        <span className={`badge badge-sm ${statusBadgeClass(job.status)}`}>{job.status}</span>
        {blockedDep && (
          <div className="badge badge-xs badge-warning badge-outline mt-1 font-mono gap-1">
            <Lock size={9} /> awaits {shortId(blockedDep)}
          </div>
        )}
        {job.scheduled_at && new Date(job.scheduled_at).getTime() > now && job.status === 'pending' && (
          <div className="text-xs text-info/70 font-mono mt-0.5">
            {inFuture(job.scheduled_at, now)}
          </div>
        )}
      </td>
      <td className="font-mono">
        <span className={job.retry_count > 0 ? 'text-warning' : ''}>
          {job.retry_count}/{job.max_retries}
        </span>
      </td>
      <td className="font-mono text-xs whitespace-nowrap">
        {new Date(job.scheduled_at).getTime() > now
          ? inFuture(job.scheduled_at, now)
          : '—'}
      </td>
      <td className="text-xs whitespace-nowrap">
        {job.interval ? (
          <span className="badge badge-sm badge-info badge-outline">
            {INTERVAL_LABEL[job.interval] ?? job.interval}
          </span>
        ) : (
          <span className="text-base-content/40">once</span>
        )}
      </td>
      <td className="font-mono text-xs whitespace-nowrap">
        {timeAgo(job.created_at, now)}
      </td>
      <td>
        {cancellable && (
          <button
            className="btn btn-error btn-xs"
            onClick={() => onCancel(job.id)}
          >
            <X size={12} /> Cancel
          </button>
        )}
      </td>
    </tr>
  );
}
