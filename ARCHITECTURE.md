# Architecture Document — Dilamme Background Job Scheduler

**Author:** Junior Systems Engineer
**Date:** 12 June 2026
**Repository:** https://github.com/kaosi-anikwe/job-scheduler

---

## 1. Executive Summary

The Dilamme Background Job Scheduler is a production-grade asynchronous job
execution platform designed for self-managed bare-metal deployment.  It decouples
job submission (FastAPI), scheduling (heap or timing wheel), execution
(independent worker pool), and observability (WebSocket-driven React dashboard)
into isolated processes that communicate through PostgreSQL (source of truth) and
Redis (lock manager + pub/sub bus).

The system guarantees:
- **No double-allocation** — Redis-based distributed locks with Lua-script-safe release
- **Starvation prevention** — virtual-rank aging formula that promotes long-waiting jobs
- **Crash resilience** — all state is durable in PostgreSQL; memory loss never corrupts jobs
- **DAG workflow support** — jobs can declare parent dependencies; cycle detection at creation time
- **Automatic retry + DLQ** — exponential backoff with jitter, dead-letter queue with email alerting
- **Live observability** — WebSocket push of every state transition to the operations dashboard

---

## 2. Component Topology

```
                         ┌──────────────────┐
                         │   React SPA       │
                         │  (Vite + daisyUI) │
                         └──────┬───────────┘
                                │ HTTPS (wss:// for WS)
                         ┌──────┴───────────┐
                         │   Nginx           │
                         │  Reverse Proxy    │
                         │  HTTP/2 + TLS     │
                         └──────┬───────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │ /api/*  /docs   │ /ws/*            │ / (static)
              ▼                 ▼                  ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │  FastAPI API  │  │  FastAPI WS  │  │  Vite Build   │
    │  (uvicorn)    │  │  Endpoint    │  │  Static Files │
    └──────┬───────┘  └──────┬───────┘  └──────────────┘
           │                 │
    ┌──────┼─────────────────┼──────────────────────┐
    │      ▼                 ▼                      │
    │  ┌─────────┐    ┌─────────────┐               │
    │  │PostgreSQL│    │   Redis     │               │
    │  │ (state)  │    │(locks+pubsub)│              │
    │  └────▲─────┘    └──────┬──────┘               │
    │       │                 │                      │
    │  ┌────┴─────────────────┴─────┐                │
    │  │       Worker Process        │               │
    │  │  ┌───────────────────────┐ │               │
    │  │  │   Scheduler Loop      │ │               │
    │  │  │  (heap or timing wheel)│ │               │
    │  │  └──────────┬────────────┘ │               │
    │  │             ▼              │               │
    │  │  ┌───────────────────────┐ │               │
    │  │  │   Worker Pool (×N)    │ │               │
    │  │  │  Lock → Execute → Log │ │               │
    │  │  └───────────────────────┘ │               │
    │  │  ┌───────────────────────┐ │               │
    │  │  │  Recovery: Retry/DLQ  │ │               │
    │  │  │  Cancellation Listener│ │               │
    │  │  └───────────────────────┘ │               │
    │  └────────────────────────────┘               │
    └───────────────────────────────────────────────┘
```

**Key isolation properties:**
- The API **never blocks on job execution**. It writes to the database and publishes events.
- The worker **runs independently** via `uv run --package worker python -m worker`.
- PostgreSQL is the single source of truth for all job state.
- Redis is used as a volatile cache/lock/pub-sub layer — no durable data is stored there.

---

## 3. Monorepo Structure

```
job-scheduler/
├── backend/                          # uv workspace root
│   ├── pyproject.toml               # Workspace definition, dev deps
│   ├── alembic/                     # Database migrations
│   │   ├── env.py
│   │   └── versions/
│   │       └── 3499ddaccae7_initial_migration.py
│   └── packages/
│       ├── shared/                  # Library — imported by api + worker
│       │   └── src/shared/
│       │       ├── config.py        # pydantic-settings (env vars)
│       │       ├── database.py      # AsyncEngine singleton
│       │       ├── redis.py         # Redis connection + pubsub
│       │       ├── dag.py           # Cycle detection (DFS)
│       │       ├── logging.py       # Structured JSON logger
│       │       ├── models/          # SQLAlchemy ORM models
│       │       │   ├── job.py
│       │       │   ├── job_dependency.py
│       │       │   └── execution_log.py
│       │       └── schemas/         # Pydantic v2 request/response
│       │           ├── job.py
│       │           ├── execution_log.py
│       │           ├── websocket.py
│       │           └── worker.py
│       ├── api/                     # FastAPI HTTP + WebSocket server
│       │   └── src/api/
│       │       ├── main.py          # App factory, lifespan, CORS
│       │       ├── deps.py          # FastAPI dependency injection
│       │       ├── routers/
│       │       │   ├── health.py
│       │       │   ├── jobs.py      # CRUD, cancel, dashboard stats
│       │       │   ├── dlq.py       # Dead-letter queue endpoints
│       │       │   └── workers.py   # Fleet status, scheduler info
│       │       ├── services/
│       │       │   ├── job_service.py
│       │       │   └── event_publisher.py
│       │       └── websocket/
│       │           └── manager.py   # ConnectionManager + Redis bridge
│       └── worker/                  # Scheduler + executor + handlers
│           └── src/worker/
│               ├── main.py          # Entry point, orchestration
│               ├── scheduler/
│               │   ├── heap_scheduler.py   # Min-heap with V-rank
│               │   ├── timing_wheel.py     # Hashed timing wheel
│               │   ├── dag_resolver.py     # Ready-job query
│               │   └── benchmark.py        # Heap vs. wheel benchmark
│               ├── executor/
│               │   ├── worker_pool.py      # Async worker pool
│               │   └── lock_manager.py     # Redis distributed locks
│               ├── handlers/
│               │   ├── base.py
│               │   ├── email_handler.py    # MIME construction + SMTP sim
│               │   ├── webhook_handler.py  # HTTP POST simulation
│               │   ├── log_handler.py      # Structured log processing
│               │   └── registry.py
│               └── recovery/
│                   ├── retry.py            # Backoff with jitter
│                   ├── dlq.py              # DLQ threshold + email alert
│                   └── cancellation.py     # Redis Pub/Sub cancellation
├── frontend/                         # React dashboard (Vite + daisyUI)
│   ├── package.json
│   ├── vite.config.ts               # Dev proxy → :8000
│   └── src/
│       ├── sdk/                     # hey-api generated client (gitignored)
│       ├── app/
│       │   ├── App.tsx
│       │   ├── lib/
│       │   │   ├── api.ts           # hey-api client config
│       │   │   ├── services.ts      # Typed API wrappers
│       │   │   ├── websocket.tsx     # WebSocket provider + reconnection
│       │   │   ├── hooks.ts         # Data-fetching + mutation hooks
│       │   │   ├── types.ts         # UI types, label maps, constants
│       │   │   └── format.ts        # Display formatters
│       │   ├── pages/
│       │   │   ├── Layout.tsx
│       │   │   └── Dashboard.tsx
│       │   └── components/
│       │       ├── Sidebar.tsx
│       │       ├── WorkerFleet.tsx
│       │       ├── StatsGrid.tsx
│       │       ├── JobsTable.tsx
│       │       ├── CreateJobModal.tsx
│       │       ├── DlqView.tsx
│       │       └── LogsPanel.tsx
│       └── styles/
│           └── index.css            # Tailwind CSS v4 + daisyUI 5
└── deploy/
    ├── nginx.conf                   # Nginx site config (sites-enabled/)
    ├── start_api.sh                 # Migrations + uvicorn
    ├── start_worker.sh              # Worker entry
    └── systemd/
        ├── api.service
        └── worker.service
```

---

## 4. Data Model

### 4.1 PostgreSQL Schema

Three tables form the persistent state:

```
┌─────────────────────────────────────────────┐
│ jobs                                        │
├─────────────────────────────────────────────┤
│ id           UUID (PK)                      │
│ type         VARCHAR(50)                    │
│ priority     SMALLINT (1=High, 2=Med, 3=Low)│
│ status       VARCHAR(20)                    │
│              (pending|processing|completed   │
│               |failed|cancelled)             │
│ payload      JSONB                          │
│ error_details JSONB (nullable)               │
│ retry_count  INTEGER                        │
│ max_retries  INTEGER                        │
│ scheduled_at TIMESTAMPTZ                    │
│ interval     VARCHAR(30) (nullable)          │
│ created_at   TIMESTAMPTZ                    │
│ updated_at   TIMESTAMPTZ                    │
└─────────────────────────────────────────────┘
        │                    │
        │ (FK)               │ (FK)
        ▼                    ▼
┌───────────────────┐  ┌──────────────────────┐
│ job_dependencies   │  │ execution_logs        │
├───────────────────┤  ├──────────────────────┤
│ parent_job_id UUID │  │ id         INTEGER   │
│ child_job_id  UUID │  │ job_id     UUID (FK) │
│ (composite PK)     │  │ event_type VARCHAR   │
└───────────────────┘  │ log_data   JSONB     │
                       │ created_at TIMESTAMPTZ│
                       └──────────────────────┘
```

### 4.2 Job Lifecycle State Machine

```
 create
   │
   ▼
 pending ──────────────────────────► cancelled
   │                                    ▲
   │ (scheduled_at ≤ now                │
   │  & deps completed)                 │
   ▼                                    │
 processing ────(cancellation signal)───┘
   │
   ├── success ──► completed ──(recurring)──► pending (clone)
   │
   └── failure ──► retry (backoff, retry_count++)
        │              │
        │              └──(retries < max)──► pending
        │
        └──(retries ≥ max)──► failed (DLQ) ──(manual retry)──► pending
```

All transitions are recorded as structured `ExecutionLog` rows and broadcast
via Redis Pub/Sub to connected WebSocket clients.

---

## 5. Scheduling Engine

### 5.1 Heap-Based Priority Queue (Primary)

**Data structure:** Binary min-heap (`heapq`-backed, asyncio-locked)

**Ordering (3-tier comparison):**

1. **Virtual rank** (lower = higher priority): `V = base_priority + (1.0 / 3600.0) × scheduled_at`
2. **Scheduled time** (earlier wins)
3. **Creation time** (earlier wins)

**Starvation prevention (aging):** A job waiting 1 hour past its scheduled time
gains a full priority tier improvement. The virtual rank is computed **once on
heap insertion** and does not change — no in-place mutation of heap nodes.
The aging is baked into the immutable rank at entry time, so a job that has been
eligible for a long time naturally overtakes newer high-priority jobs.

**Key design decisions:**
- Only **ready-to-run** jobs enter the heap (scheduled_at ≤ now, all DAG
  dependencies completed). Future jobs and blocked jobs stay in PostgreSQL.
- Recurring jobs automatically clone themselves (new `pending` row with
  `scheduled_at = now + interval`) on successful completion.
- **No backpressure** — the scheduler loop polls every 1s and feeds the heap;
  idle workers poll the heap with a 0.5s backoff.

### 5.2 Hashed Timing Wheel (Alternative)

**Data structure:** Circular array of 60 slots, 1s tick duration.

**Algorithm:**
- `add_job`: O(1) — computes `target_slot = (current_slot + total_ticks) % num_slots`
- `tick`: O(k) where k = jobs in the current slot; advances the wheel pointer
- Jobs with delays exceeding one full wheel rotation are tracked with
  `remaining_rounds` — only fired when rounds reach 0.

**Tradeoffs vs. Heap:**

| Property | Heap | Timing Wheel |
|---|---|---|
| Insert | O(log n) | O(1) |
| Extract-min | O(log n) | O(k) per tick |
| Priority ordering | Strict (3-tier sort) | FIFO within a slot |
| Aging | Virtual rank formula | None |
| Best for | Mixed-priority workloads | High-volume timed events |
| Configuration toggle | `SCHEDULER_ENGINE=heap` | `SCHEDULER_ENGINE=timing_wheel` |

### 5.3 Benchmark Results

Run with: `uv run --package worker python -m worker.scheduler.benchmark`

| Jobs | Heap Insert (p50) | Wheel Insert (p50) | Heap Extract (p50) | Wheel Extract (p50) |
|------|-------------------|-------------------|---------------------|----------------------|
| 100 | 1.20µs | 1.20µs | 1.70µs | 1.35µs |
| 1,000 | 1.20µs | 1.20µs | 2.10µs | 2.50µs |
| 10,000 | 1.20µs | 1.20µs | 2.90µs | 15.90µs |
| 100,000 | 1.30µs | 1.30µs | 5.60µs | 257.40µs |

**Observation:** The heap wins on extract at scale because O(log n) degrades
gracefully while the wheel's per-tick O(k) depends on slot density. At 10K+
jobs, the wheel's extract cost grows linearly with the number of jobs in each
tick slot. The wheel's O(1) insert shines for high-volume scheduling (e.g.,
thousands of jobs per second) where extract ordering is secondary.

---

## 6. DAG Workflow (Directed Acyclic Graph)

**Model:** The `job_dependencies` table stores explicit parent → child edges.
A job's `dependency_ids` are declared at creation time.

**Cycle detection:** The `validate_no_cycles` function in `shared.dag` runs a
DFS from each proposed parent upward through existing edges. If the new job is
reachable from any parent, the creation is rejected with HTTP 400. This check
runs synchronously within the `POST /api/v1/jobs` request.

**Readiness gate:** The scheduler's `get_ready_jobs` query uses a `NOT EXISTS`
subquery that checks whether every parent of a `pending` job has reached
`completed` status. Blocked jobs remain in PostgreSQL and never enter the heap.

**Example 3-step workflow:**

```
Generate Report (log_processing, priority 1)
       ↓
Upload File    (webhook, priority 1, depends_on=[report.id])
       ↓
Send Email     (send_email, priority 1, depends_on=[upload.id])
```

---

## 7. Concurrency Control & Duplicate Protection

### 7.1 Redis Distributed Locks

Every worker acquires an exclusive lock before processing a job:

```
SET lock:job:<uuid> <worker_id> NX PX 30000
```

- **NX** (Not eXists) — only succeeds if no lock is held
- **PX 30000** — auto-expires after 30s (prevents orphaned locks on crash)

**Safe release:** A Lua script (`GET` + compare + `DEL`) ensures a worker only
releases its own lock — expired locks owned by a different worker are never
deleted by the wrong process. A `LockManager.extend()` method allows
long-running jobs to refresh their TTL.

### 7.2 In-Memory Guard

Within a single worker process, the `WorkerPool` tracks `_inflight` jobs in
a dict. The heap's `_job_ids` set prevents duplicate pushes. These are
process-local safety nets; the Redis lock is the authoritative distributed guard.

---

## 8. Retry, Backoff, & Dead-Letter Queue

### 8.1 Retry Policy

- **Max retries:** 3 (configurable per job via `max_retries` column)
- **Backoff formula:** `T_wait = 5^(attempt - 1) + Uniform(0, 1.5)`
- **Jitter:** Random uniform jitter (±0.75s) prevents thundering herd on
  shared failure causes (e.g., external API outage)

| Attempt | Approximate delay |
|---------|------------------|
| 1 | ~1s |
| 2 | ~5s |
| 3 | ~25s |

A failed job transitions back to `pending` with a `next_retry_at` timestamp.
The scheduler skips jobs whose retry window has not yet elapsed.

### 8.2 Dead-Letter Queue (DLQ)

Jobs that fail after all retries are permanently marked `failed` with
`error_details` populated. The DLQ is queryable via `GET /api/v1/dlq`.

**Alert threshold:** When ≥ 10 jobs accumulate in the DLQ (configurable via
`DLQ_ALERT_THRESHOLD`), a structured log event is emitted and an SMTP email
alert is dispatched to the configured `DLQ_ALERT_EMAIL` address.

**Manual retry:** `POST /api/v1/dlq/{job_id}/retry` resets `retry_count` to 0,
sets status back to `pending`, clears `error_details`, and allows the job to
re-enter the scheduler. If it fails again after exhausting retries, it returns
to the DLQ.

---

## 9. Cooperative Cancellation

### 9.1 Decision: Cancelling an In-Flight Job

When `PATCH /api/v1/jobs/{id}/cancel` is called on a `processing` job, a
cancellation signal is published to Redis Pub/Sub on the `cancel:{job_id}`
channel. The `CancellationListener` running in the worker process receives
this signal and calls `WorkerPool.cancel_job()`, which cancels the tracked
`asyncio.Task`.

**Result:** The handler's `CancelledError` is caught in `_process_job`, the
job's status is updated to `cancelled`, and the result is discarded. This is a
cooperative (not preemptive) cancellation — the handler must yield to the event
loop for the cancellation to take effect. Long-running CPU-bound handlers may
not cancel instantly.

Cancelling a `pending` job simply updates its status directly — no signal
needed.

---

## 10. Real-Time Updates (WebSocket)

### 10.1 Event Pipeline

```
Job state change
       │
       ▼
  publish_event()
       │
       ├─► PostgreSQL (execution_logs table)
       │
       └─► Redis Pub/Sub (channel: jobs:events)
              │
              ▼
       ConnectionManager._redis_listener()
              │
              ▼
       Fan-out to all connected WebSocket clients
```

### 10.2 WebSocket Message Format

```json
{
  "event": "JOB_STARTED",
  "job_id": "41bd37bf-cdc3-43e5-8965-b06fbc46afaf",
  "data": {"worker_node": "worker_0_9a964172"},
  "timestamp": "2026-06-12T15:47:00Z"
}
```

**8 event types:** `JOB_CREATED`, `JOB_STARTED`, `RETRY_ATTEMPTED`, `JOB_FAILED`,
`JOB_CANCELLED`, `JOB_COMPLETED`, `JOB_RETRIED_FROM_DLQ`, `RECURRING_SCHEDULED`.

### 10.3 Frontend WebSocket Resilience

The React `WebSocketProvider` implements exponential backoff reconnection:
- Initial delay: 1s
- Max delay: 30s
- Formula: `min(1000 × 2^(attempt), 30000)` ms

The provider exposes a `ConnectionStatus` (`CONNECTING` | `OPEN` | `CLOSED`)
used by the Sidebar telemetry badge and the LogsPanel.

---

## 11. Worker Fleet Heartbeats

Each worker publishes a JSON blob to `worker:heartbeat:{worker_id}` every 2
seconds:

```json
{
  "worker_id": "worker_0_9a964172",
  "status": "running",
  "job_id": "41bd37bf-cdc3-43e5-8965-b06fbc46afaf",
  "job_type": "send_email",
  "started_at": "2026-06-12T15:46:58Z",
  "ts": "2026-06-12T15:47:00Z"
}
```

The endpoint `GET /api/v1/workers` scans all heartbeat keys via `SCAN
worker:heartbeat:*` and returns an aggregated `WorkerFleetStatus`. Heartbeats
have a 5-second TTL — workers that stop publishing disappear from the fleet view.

---

## 12. Frontend Architecture

### 12.1 Stack

| Concern | Technology |
|---|---|
| Framework | React 18 |
| Language | TypeScript 5 (strict mode) |
| Build | Vite 6 |
| Styling | daisyUI 5 (Tailwind CSS 4), `dim` theme |
| API Client | hey-api (generated from FastAPI OpenAPI schema) |
| Real-time | WebSocket (exponential backoff reconnect) |
| Routing | React Router v7 |
| Toasts | sonner |

### 12.2 Type-Safe API Layer

The `hey-api` CLI generates a fully typed TypeScript SDK from the running
backend's `openapi.json`. The generated client is configured with an empty base
URL so all requests go through the same-origin Nginx proxy. The SDK is
**not committed** to git — it is regenerated on every `npm run dev` and
`npm run build`.

### 12.3 Component Hierarchy

```
App
├── WebSocketProvider
└── BrowserRouter
    └── Layout
        ├── Sidebar
        │   ├── Brand (Dilamme logo + name)
        │   ├── Telemetry badge (WebSocket status)
        │   ├── Scheduler engine badge (Heap/Timing Wheel)
        │   └── Navigation (Dashboard, DLQ)
        └── Routes
            ├── Dashboard
            │   ├── StatsGrid (counts by status)
            │   ├── WorkerFleet (live heartbeat bays)
            │   ├── JobsTable (paginated, filterable)
            │   ├── CreateJobModal (form with DAG wiring)
            │   └── LogsPanel (real-time event stream)
            └── DlqView
                ├── Threshold alert banner
                └── Collapsible failed-job cards with retry buttons
```

### 12.4 Starvation Aging (Frontend Display)

The `effectivePriority()` function mirrors the backend's heap formula. When a
job's computed effective priority differs from its base priority, a `↑ aged`
badge appears next to the priority column. The aging window is 1 hour per
tier — matching the backend's `alpha = 1.0 / 3600.0`.

---

## 13. Deployment Architecture

### 13.1 Server Stack

- **OS:** Ubuntu 24.04 LTS (bare-metal or EC2)
- **Web server:** Nginx (reverse proxy, TLS termination)
- **App server:** Uvicorn (2 workers, managed by systemd)
- **Worker:** Standalone Python process (managed by systemd)
- **Database:** PostgreSQL 16
- **Cache/Pub-Sub:** Redis 7

### 13.2 Nginx Routing

| Path | Destination |
|---|---|
| `/api/*` | `http://127.0.0.1:8000` (uvicorn) |
| `/ws/*` | `http://127.0.0.1:8000` (WebSocket upgrade) |
| `/docs`, `/redoc`, `/openapi.json` | `http://127.0.0.1:8000` |
| `/` + static assets | `/var/www/scheduler-ui` (Vite build output) |

All HTTP/80 traffic is redirected to HTTPS/443. TLS is provisioned via
Let's Encrypt (certbot).

### 13.3 systemd Unit Design

Both `api.service` and `worker.service`:
- Run as user `ubuntu`, group `ubuntu`
- Read environment from `/opt/dilamme-scheduler/backend/.env`
- Include `/home/ubuntu/.local/bin` on PATH (for `uv`)
- Use `ProtectSystem=strict` with `ReadWritePaths=/opt/dilamme-scheduler`
- Auto-restart on failure with rate-limited burst protection
- Log to journald with distinct `SyslogIdentifier` tags

### 13.4 Startup Sequence

```
start_api.sh:                  start_worker.sh:
  1. alembic upgrade head        1. python -m worker
  2. uvicorn api.main:app            ├── Scheduler loop (1s poll)
     --host 0.0.0.0                  ├── Worker pool (×N)
     --workers 2                     ├── Cancellation listener
     --port 8000                     └── DLQ monitor (60s poll)
```

---

## 14. Configuration Reference

All knobs are environment variables, set in `backend/.env`:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | (required) | PostgreSQL async connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `WORKER_CONCURRENCY` | 4 | Number of async worker tasks |
| `SCHEDULER_ENGINE` | `heap` | `heap` or `timing_wheel` |
| `DLQ_ALERT_THRESHOLD` | 10 | Jobs in DLQ before alert fires |
| `DLQ_ALERT_EMAIL` | `admin@dilamme.com` | Alert recipient address |
| `SMTP_HOST` | `localhost` | SMTP server for DLQ alerts |
| `SMTP_PORT` | 1025 | SMTP port (Mailpit dev default) |
| `LOG_LEVEL` | `INFO` | Structured log verbosity |
| `API_HOST` | `0.0.0.0` | Uvicorn bind address |
| `API_PORT` | 8000 | Uvicorn listen port |
| `API_WORKERS` | 2 | Uvicorn worker processes |

---

## 15. Key Design Decisions & Rationale

| Decision | Rationale |
|---|---|
| PostgreSQL as source of truth | ACID guarantees; crash-resilient; no data loss on worker restart |
| Redis as volatile layer only | Best-effort pub/sub + locks; no durable state stored in Redis |
| Immutable virtual rank | No in-place heap mutation needed; O(log n) reheapify avoided |
| Cooperative cancellation | Python's asyncio cancellation is cooperative by nature; preemptive would require OS signals |
| `ProtectSystem=strict` in systemd | Defense-in-depth: even if the service is compromised, system binaries are read-only |
| hey-api SDK gitignored | Derived artifact; regenerated on every build; pinning it risks schema drift |
| daisyUI over shadcn/MUI | No JS runtime overhead; pure CSS classes; `dim` theme fits ops dashboard aesthetic |
| 1-hour aging window | Tradeoff: long enough to prevent thrashing, short enough that no job waits forever; empirically aligns with on-call SLO windows |
