import { NavLink } from 'react-router';
import { LayoutDashboard, Skull, Boxes, Cpu } from 'lucide-react';
import { useStats, useSchedulerInfo } from '../lib/hooks';
import { useWebSocket } from '../lib/websocket';

export function Sidebar() {
  const { stats } = useStats();
  const { status } = useWebSocket();
  const schedulerInfo = useSchedulerInfo();
  const dlqCount = stats.failed ?? 0;
  const activeCount = stats.processing ?? 0;

  return (
    <aside className="w-64 bg-base-200 flex flex-col border-r border-base-300 shrink-0">
      <div className="p-5 flex items-center gap-2.5">
        <div className="grid place-items-center size-9 rounded-lg bg-primary/15 text-primary">
          <Boxes size={20} />
        </div>
        <div>
          <div className="font-display font-bold leading-tight">Dilamme</div>
          <div className="text-xs text-base-content/50 font-mono tracking-tight">job scheduler</div>
        </div>
      </div>

      <div className="mx-5 mb-2 rounded-lg bg-base-300/40 px-3 py-2.5 flex items-center justify-between">
        <span className="text-xs text-base-content/60">Engine</span>
        {status === 'OPEN' && (
          <span className="badge badge-success badge-sm gap-1.5 font-medium">
            <span className="inline-block size-1.5 rounded-full bg-current animate-pulse" />
            Live
          </span>
        )}
        {status === 'CONNECTING' && (
          <span className="badge badge-warning badge-sm gap-1.5 font-medium animate-pulse">
            Reconnecting
          </span>
        )}
        {status === 'CLOSED' && (
          <span className="badge badge-error badge-sm gap-1.5">Offline</span>
        )}
      </div>

      {schedulerInfo && (
        <div className="mx-5 mb-2 rounded-lg bg-base-300/40 px-3 py-2.5 flex items-center justify-between">
          <span className="text-xs text-base-content/60 flex items-center gap-1">
            <Cpu size={10} />
            Scheduler
          </span>
          <span className="badge badge-sm font-mono">
            {schedulerInfo.engine === 'heap' ? 'Heap' : 'Timing Wheel'}
          </span>
        </div>
      )}

      <nav className="px-3 mt-2 flex-1">
        <ul className="menu w-full gap-1 p-0">
          <li>
            <NavLink to="/" end className={({ isActive }) => (isActive ? 'menu-active' : '')}>
              <LayoutDashboard size={18} />
              <span>Dashboard</span>
              {activeCount > 0 && (
                <span className="badge badge-sm badge-warning ml-auto font-mono">{activeCount}</span>
              )}
            </NavLink>
          </li>
          <li>
            <NavLink to="/dlq" className={({ isActive }) => (isActive ? 'menu-active' : '')}>
              <Skull size={18} />
              <span>Dead-Letter Queue</span>
              {dlqCount > 0 && (
                <span className="badge badge-sm badge-error ml-auto font-mono">{dlqCount}</span>
              )}
            </NavLink>
          </li>
        </ul>
      </nav>

      <div className="p-3 m-2 rounded-lg bg-base-300/40 text-center">
        <span className="text-xs text-base-content/40 font-mono">Dilamme v0.1</span>
      </div>
    </aside>
  );
}
