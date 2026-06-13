import { useRef, useEffect, useState, useCallback } from 'react';
import { X, AlertTriangle, GitBranch, Clock, Copy } from 'lucide-react';
import { fetchJob, fetchJobLogs } from '../lib/services';
import type { JobResponse, ExecutionLogResponse } from '../lib/services';
import { useWebSocket } from '../lib/websocket';
import { statusBadgeClass, priorityTextClass, timeAgo, shortId } from '../lib/format';
import { JOB_TYPE_LABEL, PRIORITY_LABEL, INTERVAL_LABEL } from '../lib/types';

/* ------------------------------------------------------------------ */
/* Event timeline colours                                              */
/* ------------------------------------------------------------------ */

const EVENT_DOT: Record<string, string> = {
  JOB_CREATED: 'bg-info',
  JOB_STARTED: 'bg-warning',
  JOB_COMPLETED: 'bg-success',
  JOB_FAILED: 'bg-error',
  JOB_CANCELLED: 'bg-neutral',
  RETRY_ATTEMPTED: 'bg-warning',
  RECURRING_SCHEDULED: 'bg-info',
  JOB_RETRIED_FROM_DLQ: 'bg-primary',
};

/* ------------------------------------------------------------------ */
/* Small component that fetches + renders a single dependency job      */
/* ------------------------------------------------------------------ */

function DepJobRow({ jobId }: { jobId: string }) {
  const [job, setJob] = useState<JobResponse | null>(null);

  useEffect(() => {
    fetchJob(jobId).then(setJob).catch(() => { });
  }, [jobId]);

  if (!job) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-base-300 px-3 py-2 text-xs font-mono text-base-content/40">
        <span className="loading loading-xs" />
        {shortId(jobId)}
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between rounded-lg border border-base-300 px-3 py-2 text-xs gap-3">
      <div className="flex items-center gap-2 min-w-0">
        <span className={`badge badge-xs shrink-0 ${statusBadgeClass(job.status)}`}>{job.status}</span>
        <span className="font-mono shrink-0">{shortId(job.id)}</span>
        <span className="text-base-content/60 truncate">{JOB_TYPE_LABEL[job.type] ?? job.type}</span>
      </div>
      <span className={`font-semibold shrink-0 ${priorityTextClass(job.priority)}`}>
        {PRIORITY_LABEL[job.priority] ?? job.priority}
      </span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Main modal                                                          */
/* ------------------------------------------------------------------ */

export function JobDetailModal({ jobId, onClose }: { jobId: string; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [job, setJob] = useState<JobResponse | null>(null);
  const [logs, setLogs] = useState<ExecutionLogResponse[]>([]);
  const { lastMessage } = useWebSocket();

  const load = useCallback(() => {
    fetchJob(jobId).then(setJob).catch(() => { });
    fetchJobLogs(jobId).then(setLogs).catch(() => { });
  }, [jobId]);

  // Initial load
  useEffect(() => { load(); }, [load]);

  // Live-update when a WS event touches this job
  useEffect(() => {
    if (lastMessage?.job_id === jobId) load();
  }, [lastMessage, jobId, load]);

  // Open dialog
  useEffect(() => {
    ref.current?.showModal();
  }, []);

  const now = Date.now();
  const deps = job?.dependency_ids ?? [];

  const meta: [string, React.ReactNode][] = job
    ? [
      ['Job ID', (
        <button
          key="id"
          className="font-mono text-xs flex items-center gap-1 hover:text-primary"
          title="Click to copy"
          onClick={() => navigator.clipboard?.writeText(job.id)}
        >
          {shortId(job.id)} <Copy size={10} className="opacity-60" />
        </button>
      )],
      ['Priority', (
        <span key="p" className={`font-bold ${priorityTextClass(job.priority)}`}>
          {PRIORITY_LABEL[job.priority] ?? job.priority}
        </span>
      )],
      ['Retries', (
        <span key="r" className={`font-mono ${job.retry_count > 0 ? 'text-warning' : ''}`}>
          {job.retry_count} / {job.max_retries}
        </span>
      )],
      ['Scheduled', <span key="s" className="font-mono text-xs">{new Date(job.scheduled_at).toLocaleString()}</span>],
      ['Created', <span key="c" className="font-mono text-xs">{timeAgo(job.created_at, now)}</span>],
      ['Updated', <span key="u" className="font-mono text-xs">{timeAgo(job.updated_at, now)}</span>],
      ...(job.interval
        ? [['Interval', (
          <span key="i" className="badge badge-sm badge-info badge-outline">
            {INTERVAL_LABEL[job.interval] ?? job.interval}
          </span>
        )] as [string, React.ReactNode]]
        : []),
    ]
    : [];

  return (
    <dialog
      ref={ref}
      className="modal"
      onClose={onClose}
    >
      <div className="modal-box w-11/12 max-w-2xl max-h-[90vh] overflow-y-auto flex flex-col gap-5">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h3 className="font-display text-lg font-bold">
              {job ? (JOB_TYPE_LABEL[job.type] ?? job.type) : 'Job Details'}
            </h3>
            {job && (
              <span className={`badge ${statusBadgeClass(job.status)}`}>{job.status}</span>
            )}
          </div>
          <button className="btn btn-ghost btn-sm btn-circle" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        {!job ? (
          <div className="flex justify-center py-12">
            <span className="loading loading-spinner loading-lg" />
          </div>
        ) : (
          <>
            {/* Metadata grid */}
            <section className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-sm">
              {meta.map(([label, value]) => (
                <div key={String(label)} className="bg-base-300/50 rounded-lg p-2.5">
                  <div className="text-xs text-base-content/50 mb-1">{label}</div>
                  <div>{value}</div>
                </div>
              ))}
            </section>

            {/* Payload */}
            {Object.keys(job.payload).length > 0 && (
              <section>
                <SectionLabel>Payload</SectionLabel>
                <pre className="bg-base-300/50 rounded-lg p-3 text-xs font-mono overflow-x-auto">
                  {JSON.stringify(job.payload, null, 2)}
                </pre>
              </section>
            )}

            {/* Error details */}
            {job.error_details && Object.keys(job.error_details).length > 0 && (
              <section>
                <SectionLabel icon={<AlertTriangle size={12} />} className="text-error">
                  Error Details
                </SectionLabel>
                <pre className="bg-error/10 border border-error/30 rounded-lg p-3 text-xs font-mono overflow-x-auto text-error/90">
                  {JSON.stringify(job.error_details, null, 2)}
                </pre>
              </section>
            )}

            {/* DAG dependencies */}
            {deps.length > 0 && (
              <section>
                <SectionLabel icon={<GitBranch size={12} />}>
                  Depends On ({deps.length})
                </SectionLabel>
                <div className="flex flex-col gap-1.5">
                  {deps.map((id) => (
                    <DepJobRow key={id} jobId={id} />
                  ))}
                </div>
              </section>
            )}

            {/* Execution timeline */}
            <section>
              <SectionLabel icon={<Clock size={12} />}>
                Execution Timeline ({logs.length})
              </SectionLabel>
              {logs.length === 0 ? (
                <p className="text-xs text-base-content/40 italic">No events recorded yet.</p>
              ) : (
                <ol className="relative border-l border-base-300 ml-2 flex flex-col gap-4">
                  {logs.map((log) => (
                    <li key={log.id} className="ml-4">
                      <span
                        className={`absolute -left-1.5 mt-0.5 size-3 rounded-full border-2 border-base-200 ${EVENT_DOT[log.event_type] ?? 'bg-neutral'}`}
                      />
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-mono text-xs font-semibold">{log.event_type}</span>
                        <span className="text-xs text-base-content/40 font-mono">
                          {new Date(log.created_at).toLocaleTimeString([], {
                            hour: '2-digit',
                            minute: '2-digit',
                            second: '2-digit',
                          })}
                        </span>
                      </div>
                      {Object.keys(log.log_data).length > 0 && (
                        <pre className="text-xs font-mono text-base-content/50 mt-1 whitespace-pre-wrap wrap-break-word">
                          {JSON.stringify(log.log_data, null, 2)}
                        </pre>
                      )}
                    </li>
                  ))}
                </ol>
              )}
            </section>
          </>
        )}
      </div>

      {/* Backdrop click closes */}
      <form method="dialog" className="modal-backdrop">
        <button onClick={onClose}>close</button>
      </form>
    </dialog>
  );
}

/* ------------------------------------------------------------------ */
/* Small helper                                                        */
/* ------------------------------------------------------------------ */

function SectionLabel({
  children,
  icon,
  className = '',
}: {
  children: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`flex items-center gap-1.5 text-xs font-semibold text-base-content/60 uppercase tracking-wide mb-2 ${className}`}>
      {icon}
      {children}
    </div>
  );
}
