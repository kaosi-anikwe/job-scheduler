import { Cpu } from 'lucide-react';
import type { WorkerFleetStatus, WorkerState } from '../lib/services';
import { JOB_TYPE_LABEL } from '../lib/types';
import { shortId } from '../lib/format';

/**
 * Shows each worker bay from real backend heartbeats.
 * Falls back to a skeleton state when the worker process is down.
 */
export function WorkerFleet({ fleet }: { fleet: WorkerFleetStatus }) {
  const { workers = [], total_workers, busy_workers } = fleet;

  // If no heartbeats received yet, show skeleton based on concurrency hint
  const displayWorkers: (WorkerState | null)[] =
    workers.length > 0
      ? workers
      : Array.from({ length: total_workers || 1 }, () => null);

  return (
    <div className="rounded-box border border-base-300 bg-base-200">
      <div className="flex items-center gap-2 px-4 pt-3 pb-2">
        <Cpu size={15} className="text-base-content/50" />
        <span className="text-xs font-medium tracking-wide text-base-content/60 uppercase">
          Worker Fleet
        </span>
        <span className="text-xs font-mono text-base-content/40 ml-auto">
          {busy_workers}/{displayWorkers.length} busy
        </span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-px bg-base-300 rounded-b-box overflow-hidden">
        {displayWorkers.map((worker, i) => (
          <Bay key={worker?.worker_id ?? `pending-${i}`} index={i} worker={worker} />
        ))}
      </div>
    </div>
  );
}

function Bay({ index, worker }: { index: number; worker: WorkerState | null }) {
  const running = worker?.status === 'running';

  return (
    <div className="bg-base-200 px-4 py-3">
      <div className="flex items-center gap-2 mb-1.5">
        <span className="font-mono text-xs text-base-content/40">
          {worker?.worker_id ?? `worker-${index + 1}`}
        </span>
        <span
          className={`ml-auto inline-flex items-center gap-1 text-xs ${
            running ? 'text-warning' : 'text-base-content/40'
          }`}
        >
          <span
            className={`size-1.5 rounded-full ${
              running ? 'bg-warning animate-pulse' : 'bg-base-content/30'
            }`}
          />
          {running ? 'running' : worker ? 'idle' : 'offline'}
        </span>
      </div>
      {running && worker ? (
        <div>
          <div className="text-sm font-medium truncate">
            {JOB_TYPE_LABEL[worker.job_type ?? ''] ?? worker.job_type}
          </div>
          {worker.job_id && (
            <div className="font-mono text-xs text-base-content/50">
              {shortId(worker.job_id)}
            </div>
          )}
        </div>
      ) : (
        <div className="text-sm text-base-content/30">
          {worker ? 'awaiting work' : 'no heartbeat'}
        </div>
      )}
    </div>
  );
}
