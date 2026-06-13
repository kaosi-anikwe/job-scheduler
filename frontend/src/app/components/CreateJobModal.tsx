import { useRef, useState } from 'react';
import { Plus, X, GitMerge } from 'lucide-react';
import { toast } from 'sonner';
import { useJobs, useCreateJob } from '../lib/hooks';
import { JOB_TYPE_LABEL, INTERVAL_LABEL } from '../lib/types';
import { shortId } from '../lib/format';
import type { JobCreate } from '../lib/services';

interface Props {
  onCreated: () => void;
}

export function CreateJobModal({ onCreated }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const { jobs } = useJobs();
  const { submit, loading } = useCreateJob();

  const [type, setType] = useState('send_email');
  const [priority, setPriority] = useState<1 | 2 | 3>(2);
  const [scheduledAt, setScheduledAt] = useState('');
  const [interval, setInterval] = useState<string>('');
  const [deps, setDeps] = useState<string[]>([]);

  // Payload fields
  const [to, setTo] = useState('test@gmail.com');
  const [subject, setSubject] = useState('Welcome');
  const [url, setUrl] = useState('https://hooks.example.com/event');
  const [lines, setLines] = useState('2048');

  const candidates = jobs.filter(
    (j) => (j.status === 'pending' || j.status === 'processing') && !deps.includes(j.id),
  );

  function buildPayload(): Record<string, unknown> {
    if (type === 'send_email') return { to, subject };
    if (type === 'webhook_delivery') return { url };
    return { lines: Number(lines) };
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const data: JobCreate = {
      type,
      priority,
      payload: buildPayload(),
      scheduled_at: scheduledAt
        ? new Date(scheduledAt).toISOString()
        : undefined,
      interval: (interval || undefined) as JobCreate['interval'],
      dependency_ids: deps.length > 0 ? deps : undefined,
    };

    let job;
    try {
      job = await submit(data);
    } catch {
      return; // interceptor already showed the toast
    }

    toast.success(
      deps.length
        ? `Queued ${shortId(job.id)} — runs after ${deps.length} job(s)`
        : `Queued ${shortId(job.id)}`,
    );
    setDeps([]);
    ref.current?.close();
    onCreated();
  }

  return (
    <>
      <button className="btn btn-primary gap-1.5" onClick={() => ref.current?.showModal()}>
        <Plus size={17} /> New job
      </button>

      <dialog ref={ref} className="modal">
        <div className="modal-box max-w-lg bg-base-200 border border-base-300">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-display font-bold">Queue a job</h2>
            <form method="dialog">
              <button className="btn btn-ghost btn-sm btn-square">
                <X size={18} />
              </button>
            </form>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <div className="form-control w-full">
              <label className="label py-1">
                <span className="label-text font-medium">Job type</span>
              </label>
              <select
                className="select select-bordered w-full"
                value={type}
                onChange={(e) => setType(e.target.value)}
              >
                {Object.entries(JOB_TYPE_LABEL).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v as string}
                  </option>
                ))}
              </select>
            </div>

            {type === 'send_email' && (
              <>
                <div className="form-control w-full">
                  <label className="label py-1">
                    <span className="label-text font-medium">Recipient</span>
                  </label>
                  <input
                    className="input input-bordered w-full"
                    value={to}
                    onChange={(e) => setTo(e.target.value)}
                    placeholder="test@gmail.com"
                  />
                </div>
                <div className="form-control w-full">
                  <label className="label py-1">
                    <span className="label-text font-medium">Subject</span>
                  </label>
                  <input
                    className="input input-bordered w-full"
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                    placeholder="Welcome"
                  />
                </div>
              </>
            )}
            {type === 'webhook_delivery' && (
              <div className="form-control w-full">
                <label className="label py-1">
                  <span className="label-text font-medium">Target URL</span>
                </label>
                <input
                  className="input input-bordered w-full"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://..."
                />
              </div>
            )}
            {type === 'log_processing' && (
              <div className="form-control w-full">
                <label className="label py-1">
                  <span className="label-text font-medium">Lines to process</span>
                </label>
                <input
                  type="number"
                  className="input input-bordered w-full"
                  value={lines}
                  onChange={(e) => setLines(e.target.value)}
                />
              </div>
            )}

            <div className="grid grid-cols-2 gap-3">
              <div className="form-control w-full">
                <label className="label py-1">
                  <span className="label-text font-medium">Priority</span>
                </label>
                <select
                  className="select select-bordered w-full"
                  value={priority}
                  onChange={(e) => setPriority(Number(e.target.value) as 1 | 2 | 3)}
                >
                  <option value={1}>High</option>
                  <option value={2}>Medium</option>
                  <option value={3}>Low</option>
                </select>
              </div>
              <div className="form-control w-full">
                <label className="label py-1">
                  <span className="label-text font-medium">Repeat</span>
                </label>
                <select
                  className="select select-bordered w-full"
                  value={interval}
                  onChange={(e) => setInterval(e.target.value)}
                >
                  <option value="">Don't repeat</option>
                  {Object.entries(INTERVAL_LABEL).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v as string}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="form-control w-full">
              <label className="label py-1 flex-col items-start gap-0.5">
                <span className="label-text font-medium">Run at</span>
                <span className="label-text-alt text-base-content/45">Leave empty to run now</span>
              </label>
              <input
                type="datetime-local"
                className="input input-bordered w-full"
                value={scheduledAt}
                onChange={(e) => setScheduledAt(e.target.value)}
              />
            </div>

            <div className="form-control w-full">
              <label className="label py-1 flex-col items-start gap-0.5">
                <span className="label-text font-medium">Run after</span>
                <span className="label-text-alt text-base-content/45">
                  Build a workflow — this job waits until the chosen jobs finish
                </span>
              </label>
              <select
                className="select select-bordered w-full"
                value=""
                onChange={(e) => e.target.value && setDeps([...deps, e.target.value])}
                disabled={candidates.length === 0}
              >
                <option value="">
                  {candidates.length ? 'Add a prerequisite…' : 'No jobs available yet'}
                </option>
                {candidates.map((j) => (
                  <option key={j.id} value={j.id}>
                    {shortId(j.id)} · {JOB_TYPE_LABEL[j.type] ?? j.type}
                  </option>
                ))}
              </select>
              {deps.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {deps.map((d) => (
                    <span key={d} className="badge badge-info badge-outline gap-1 font-mono">
                      <GitMerge size={11} /> {shortId(d)}
                      <button type="button" onClick={() => setDeps(deps.filter((x) => x !== d))}>
                        <X size={11} />
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>

            <button type="submit" className="btn btn-primary mt-2 gap-1.5" disabled={loading}>
              {loading ? (
                <span className="loading loading-spinner loading-sm" />
              ) : (
                <Plus size={16} />
              )}
              Queue job
            </button>
          </form>
        </div>
        <form method="dialog" className="modal-backdrop">
          <button>close</button>
        </form>
      </dialog>
    </>
  );
}
