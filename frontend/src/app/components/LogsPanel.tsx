import { useWebSocket } from '../lib/websocket';
import { fmtTime, shortId } from '../lib/format';
import { useState, useEffect } from 'react';

interface LogEntry {
  id: string;
  ts: number;
  event: string;
  jobId: string | null;
  message: string;
  level: 'info' | 'warn' | 'error' | 'success';
}

const DOT: Record<string, string> = {
  info: 'text-info',
  warn: 'text-warning',
  error: 'text-error',
  success: 'text-success',
};

export function LogsPanel() {
  const { lastMessage, status } = useWebSocket();
  const [logs, setLogs] = useState<LogEntry[]>([]);

  useEffect(() => {
    if (!lastMessage) return;
    const level =
      lastMessage.event === 'JOB_FAILED' || lastMessage.event === 'JOB_CANCELLED'
        ? 'error'
        : lastMessage.event === 'JOB_COMPLETED'
          ? 'success'
          : lastMessage.event === 'RETRY_ATTEMPTED'
            ? 'warn'
            : 'info';

    const entry: LogEntry = {
      id: `${lastMessage.event}-${lastMessage.job_id}-${Date.now()}`,
      ts: Date.now(),
      event: lastMessage.event,
      jobId: lastMessage.job_id,
      message: lastMessage.event,
      level: level as LogEntry['level'],
    };

    setLogs((prev) => [entry, ...prev].slice(0, 200));
  }, [lastMessage]);

  return (
    <div className="card bg-base-200 border border-base-300 shadow-xl xl:sticky xl:top-0">
      <div className="card-body p-4 gap-2">
        <div className="flex items-center justify-between">
          <h2 className="card-title font-display">Event log</h2>
          <span
            className={`badge badge-xs ${status === 'OPEN' ? 'badge-success' : status === 'CONNECTING' ? 'badge-warning' : 'badge-error'
              }`}
          >
            {status === 'OPEN' ? 'Live' : status === 'CONNECTING' ? 'Connecting' : 'Offline'}
          </span>
        </div>
        <div className="overflow-y-auto max-h-[560px] font-mono text-xs flex flex-col gap-1 pr-1">
          {logs.map((l) => (
            <div
              key={l.id}
              className="flex gap-2 items-start border-b border-base-300/50 pb-1"
            >
              <span className="text-base-content/40 shrink-0">{fmtTime(l.ts)}</span>
              <span className={`${DOT[l.level] ?? 'text-info'} shrink-0`}>●</span>
              <span className="text-secondary shrink-0">{l.event}</span>
              {l.jobId && (
                <span className="badge badge-ghost badge-xs shrink-0">{shortId(l.jobId)}</span>
              )}
              <span className="text-base-content/80">{l.message}</span>
            </div>
          ))}
          {logs.length === 0 && <div className="text-base-content/40">No events yet.</div>}
        </div>
      </div>
    </div>
  );
}
