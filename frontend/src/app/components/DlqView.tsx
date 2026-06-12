import { AlertTriangle, RotateCcw, Skull, FileWarning } from 'lucide-react';
import { toast } from 'sonner';
import { useDlq, useRetryDlqJob } from '../lib/hooks';
import { JOB_TYPE_LABEL, MAX_RETRIES } from '../lib/types';
import { shortId, timeAgo, fmtTime } from '../lib/format';
import type { JobResponse } from '../lib/services';

const DLQ_ALERT_THRESHOLD = 3;

export function DlqView() {
  const { dlqJobs, loading, refresh } = useDlq();
  const retryJob = useRetryDlqJob();
  const now = Date.now();

  const dlqSent = dlqJobs.length >= DLQ_ALERT_THRESHOLD;

  async function handleRetry(jobId: string) {
    await retryJob(jobId);
    toast.success(`Re-queued ${shortId(jobId)} from the DLQ`);
    refresh();
  }

  return (
    <div className="flex flex-col gap-5">
      <header className="flex items-center gap-3">
        <div className="grid place-items-center size-10 rounded-lg bg-error/15 text-error">
          <Skull size={20} />
        </div>
        <div>
          <h1 className="font-display font-bold">Dead-Letter Queue</h1>
          <p className="text-sm text-base-content/55">
            Jobs that used all {MAX_RETRIES} retries. Inspect the failure, then retry once it's
            fixed.
          </p>
        </div>
      </header>

      {dlqSent && (
        <div role="alert" className="alert alert-error">
          <AlertTriangle />
          <span>
            {dlqJobs.length} jobs have stalled (threshold {DLQ_ALERT_THRESHOLD}). An alert was
            dispatched to on-call.
          </span>
        </div>
      )}

      {dlqJobs.length === 0 && !loading ? (
        <div className="card bg-base-200 border border-base-300 p-12 text-center">
          <div className="text-base-content/40 flex flex-col items-center gap-2">
            <FileWarning size={28} />
            <p className="font-medium">Nothing here</p>
            <p className="text-sm">
              Jobs that exhaust their retries will show up for inspection.
            </p>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {dlqJobs.map((job) => (
            <DeadJob key={job.id} job={job} now={now} onRetry={handleRetry} />
          ))}
        </div>
      )}
    </div>
  );
}

function DeadJob({
  job,
  now,
  onRetry,
}: {
  job: JobResponse;
  now: number;
  onRetry: (id: string) => Promise<void>;
}) {
  return (
    <div className="collapse collapse-arrow bg-base-200 border border-error/30 rounded-box">
      <input type="checkbox" />
      <div className="collapse-title flex items-center gap-3 flex-wrap pr-12">
        <span className="badge badge-ghost font-mono text-xs">{shortId(job.id)}</span>
        <span className="font-medium">{JOB_TYPE_LABEL[job.type] ?? job.type}</span>
        <span className="text-error text-sm font-mono truncate max-w-full">
          {job.error_details
            ? String(Object.values(job.error_details)[0] ?? 'Unknown error')
            : 'Error details unavailable'}
        </span>
        <span className="text-xs text-base-content/45 ml-auto whitespace-nowrap">
          {timeAgo(job.created_at, now)}
        </span>
      </div>
      <div className="collapse-content">
        <div className="grid lg:grid-cols-2 gap-4 pt-1">
          <section>
            <h3 className="text-xs uppercase tracking-wide text-base-content/50 mb-2">Payload</h3>
            <div className="rounded-box border border-base-300 bg-base-100 divide-y divide-base-300">
              {Object.entries(job.payload).map(([k, v]) => (
                <div key={k} className="flex items-start gap-3 px-3 py-2">
                  <span className="font-mono text-xs text-base-content/50 w-24 shrink-0">{k}</span>
                  <span className="font-mono text-xs break-all">{String(v)}</span>
                </div>
              ))}
            </div>

            <h3 className="text-xs uppercase tracking-wide text-base-content/50 mt-4 mb-2">
              Failure details
            </h3>
            <div className="rounded-box border border-base-300 bg-base-100 divide-y divide-base-300 text-xs">
              <div className="flex items-start gap-3 px-3 py-2">
                <span className="text-base-content/50 w-24 shrink-0">Attempts</span>
                <span className="break-all">
                  {job.retry_count} of {job.max_retries}
                </span>
              </div>
              <div className="flex items-start gap-3 px-3 py-2">
                <span className="text-base-content/50 w-24 shrink-0">Last error</span>
                <span className="font-mono text-error/90 break-all">
                  {job.error_details
                    ? String(Object.values(job.error_details)[0] ?? '—')
                    : '—'}
                </span>
              </div>
              <div className="flex items-start gap-3 px-3 py-2">
                <span className="text-base-content/50 w-24 shrink-0">Entered DLQ</span>
                <span className="break-all">
                  {fmtTime(job.updated_at)} · {timeAgo(job.updated_at, now)}
                </span>
              </div>
            </div>
          </section>

          <section>
            <h3 className="text-xs uppercase tracking-wide text-base-content/50 mb-2">Stack trace</h3>
            <div className="mockup-code text-xs before:hidden bg-base-300/40">
              <pre data-prefix="✖" className="text-error">
                <code>
                  {job.error_details
                    ? JSON.stringify(job.error_details, null, 2)
                    : 'No error details'}
                </code>
              </pre>
            </div>
          </section>
        </div>

        <div className="flex items-center gap-3 mt-4">
          <button
            className="btn btn-success btn-sm gap-1.5"
            onClick={() => onRetry(job.id)}
          >
            <RotateCcw size={14} /> Retry job
          </button>
          <span className="text-xs text-base-content/45">
            Resets the retry count and sends it back to the queue.
          </span>
        </div>
      </div>
    </div>
  );
}
