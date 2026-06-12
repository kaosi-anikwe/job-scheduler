import { Cpu } from 'lucide-react';
import { useJobs } from '../lib/hooks';
import { JOB_TYPE_LABEL } from '../lib/types';
import { shortId } from '../lib/format';
import type { JobResponse } from '../lib/services';

const WORKER_COUNT = 3;

/**
 * Shows each logical worker bay and what it's currently executing.
 * Workers are simulated — real workers run independently on the backend.
 */
export function WorkerFleet() {
  const { jobs } = useJobs();
  const active = jobs.filter((j) => j.status === 'processing');
  const bays: (JobResponse | null)[] = Array.from(
    { length: WORKER_COUNT },
    (_, i) => active[i] ?? null,
  );

  return (
    <div className="rounded-box border border-base-300 bg-base-200">
      <div className="flex items-center gap-2 px-4 pt-3 pb-2">
        <Cpu size={15} className="text-base-content/50" />
        <span className="text-xs font-medium tracking-wide text-base-content/60 uppercase">
          Worker Fleet
        </span>
        <span className="text-xs font-mono text-base-content/40 ml-auto">
          {active.length}/{WORKER_COUNT} busy
        </span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-px bg-base-300 rounded-b-box overflow-hidden">
        {bays.map((job, i) => (
          <div key={i} className="bg-base-200 px-4 py-3">
            <div className="flex items-center gap-2 mb-1.5">
              <span className="font-mono text-xs text-base-content/40">worker-{i + 1}</span>
              <span
                className={`ml-auto inline-flex items-center gap-1 text-xs ${job ? 'text-warning' : 'text-base-content/40'
                  }`}
              >
                <span
                  className={`size-1.5 rounded-full ${job ? 'bg-warning animate-pulse' : 'bg-base-content/30'
                    }`}
                />
                {job ? 'running' : 'idle'}
              </span>
            </div>
            {job ? (
              <div>
                <div className="text-sm font-medium truncate">{JOB_TYPE_LABEL[job.type] ?? job.type}</div>
                <div className="font-mono text-xs text-base-content/50">{shortId(job.id)}</div>
              </div>
            ) : (
              <div className="text-sm text-base-content/30">awaiting work</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
