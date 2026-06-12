import type { Job } from './types';

/* ------------------------------------------------------------------ */
/* Badge / text classes                                                */
/* ------------------------------------------------------------------ */

export function statusBadgeClass(status: string): string {
  switch (status) {
    case 'pending':
      return 'badge-neutral';
    case 'processing':
      return 'badge-warning';
    case 'completed':
      return 'badge-success';
    case 'failed':
      return 'badge-error';
    case 'cancelled':
      return 'badge-ghost';
    default:
      return 'badge-ghost';
  }
}

export function priorityTextClass(p: number): string {
  return p === 1 ? 'text-error' : p === 2 ? 'text-warning' : 'text-base-content/50';
}

/* ------------------------------------------------------------------ */
/* Time helpers                                                        */
/* ------------------------------------------------------------------ */

export function timeAgo(ts: string | number, now: number): string {
  const t = typeof ts === 'string' ? new Date(ts).getTime() : ts;
  const s = Math.max(0, Math.floor((now - t) / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export function inFuture(ts: string | number, now: number): string {
  const t = typeof ts === 'string' ? new Date(ts).getTime() : ts;
  const s = Math.floor((t - now) / 1000);
  if (s <= 0) return 'due';
  if (s < 60) return `in ${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `in ${m}m`;
  return `in ${Math.floor(m / 60)}h`;
}

export function fmtTime(ts: string | number): string {
  const t = typeof ts === 'string' ? new Date(ts) : new Date(ts);
  return t.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export function shortId(id: string): string {
  return id.replace(/-/g, '').slice(0, 8);
}

/* ------------------------------------------------------------------ */
/* Effective priority (starvation aging)                               */
/* ------------------------------------------------------------------ */

export function effectivePriority(job: Job, now: number): number {
  const eligible = new Date(job.scheduled_at).getTime();
  const waited = now - eligible;
  const bonus = Math.floor(Math.max(0, waited) / 15_000);
  return Math.max(1, job.priority - bonus);
}
