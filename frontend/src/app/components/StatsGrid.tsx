import type { DashboardStats } from '../lib/services';

export function StatsGrid({ stats }: { stats: DashboardStats }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4">
      <Stat title="Pending" value={stats.pending ?? 0} desc="Queued / awaiting" />
      <Stat
        title="In-Flight"
        value={stats.processing ?? 0}
        valueClass={stats.processing && stats.processing > 0 ? 'text-warning animate-pulse' : ''}
        desc="Active workers"
      />
      <Stat title="Completed" value={stats.completed ?? 0} valueClass="text-success" desc="Safe milestones" />
      <Stat
        title="Failed"
        value={stats.failed ?? 0}
        valueClass={stats.failed && stats.failed > 0 ? 'text-error' : 'text-base-content/50'}
        desc="Terminal failures"
      />
      <Stat
        title="Cancelled"
        value={stats.cancelled ?? 0}
        desc="User-cancelled"
      />
    </div>
  );
}

function Stat({
  title,
  value,
  valueClass,
  desc,
}: {
  title: string;
  value: number;
  valueClass?: string;
  desc: string;
}) {
  return (
    <div className="stats shadow w-full bg-base-200 border border-base-300">
      <div className="stat">
        <div className="stat-title text-slate-400">{title}</div>
        <div className={`stat-value font-mono ${valueClass ?? ''}`}>{value}</div>
        <div className="stat-desc">{desc}</div>
      </div>
    </div>
  );
}
