import { RefreshCw } from 'lucide-react';
import { useJobs, useStats } from '../lib/hooks';
import { StatsGrid } from '../components/StatsGrid';
import { JobsTable } from '../components/JobsTable';
import { LogsPanel } from '../components/LogsPanel';
import { WorkerFleet } from '../components/WorkerFleet';
import { CreateJobModal } from '../components/CreateJobModal';

export function Dashboard() {
  const { jobs, loading, total, page, limit, refresh, setPage } = useJobs();
  const { stats } = useStats();

  return (
    <div className="flex flex-col gap-5">
      <header className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <h1 className="font-display font-bold">Operations</h1>
          <p className="text-sm text-base-content/55">
            Live view of every job moving through the fleet.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button className="btn btn-ghost gap-1.5" onClick={() => { setPage(0); refresh(); }}>
            <RefreshCw size={16} />
          </button>
          <CreateJobModal onCreated={() => { setPage(0); refresh(); }} />
        </div>
      </header>

      <WorkerFleet />
      <StatsGrid stats={stats} />

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_340px] gap-5 items-start">
        <JobsTable jobs={jobs} loading={loading} total={total} page={page} limit={limit} onPageChange={setPage} />
        <LogsPanel />
      </div>
    </div>
  );
}
