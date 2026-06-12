# Frontend — Dilamme Job Scheduler Operations Panel

React + TypeScript dashboard for monitoring and managing the background job
scheduler fleet. Provides real-time visibility into job lifecycles, a
dead-letter queue triage console, and a guided job creation form with DAG
dependency wiring.

## Stack

| Concern           | Technology                       |
| ----------------- | -------------------------------- |
| UI Framework      | React 18                         |
| Language          | TypeScript 5                     |
| Build Tool        | Vite 6                           |
| Styling           | daisyUI 5 (Tailwind CSS 4)       |
| API Client        | hey-api (generated from OpenAPI) |
| Real-Time Updates | WebSocket (auto-reconnect)       |
| Routing           | React Router v7                  |
| Toasts            | sonner                           |

## Project Structure

```
src/
├── main.tsx                  # Entry point
├── sdk/                      # Auto-generated hey-api client SDK
│   ├── client.gen.ts
│   ├── sdk.gen.ts
│   └── types.gen.ts
├── app/
│   ├── App.tsx               # Root: WebSocketProvider + Router
│   ├── lib/
│   │   ├── api.ts            # hey-api client configuration
│   │   ├── services.ts       # Typed API wrappers (jobs, DLQ, stats)
│   │   ├── websocket.tsx     # WebSocket context provider + hook
│   │   ├── hooks.ts          # Data-fetching & mutation hooks
│   │   ├── types.ts          # UI types, label maps, constants
│   │   └── format.ts         # Display formatters & helpers
│   ├── pages/
│   │   ├── Layout.tsx        # Sidebar + main content shell
│   │   └── Dashboard.tsx     # Main operations dashboard
│   └── components/
│       ├── Sidebar.tsx       # Navigation + WebSocket status badge
│       ├── WorkerFleet.tsx   # Worker bay status indicators
│       ├── StatsGrid.tsx     # Job counts by status
│       ├── JobsTable.tsx     # Filterable, sortable job list
│       ├── CreateJobModal.tsx # Job creation form with DAG wiring
│       ├── DlqView.tsx       # Dead-letter queue with retry controls
│       └── LogsPanel.tsx     # Real-time event log stream
└── styles/
    ├── index.css             # Entry point
    ├── tailwind.css          # Tailwind + daisyUI plugin
    └── fonts.css             # Space Grotesk + JetBrains Mono
```

## Getting Started

```bash
cd frontend
npm install

# Regenerate the API SDK from the backend's OpenAPI schema
# Make sure the backend is running on localhost:8000 first
curl http://localhost:8000/openapi.json -o openapi.json
npm run generate-api

# Start the dev server (proxies /api → localhost:8000, /ws → ws://localhost:8000)
npm run dev

# Production build
npm run build
```

## Key Design Decisions

### Real-Time via WebSocket

The WebSocket provider opens a connection to `wss://<host>/ws/jobs` with
exponential backoff reconnection (max 30s). Events arriving on the socket
are spliced into job lists without full page refreshes.

### Type-Safe API via hey-api

All API calls go through the auto-generated SDK in `src/sdk/`. Run
`npm run generate-api` whenever the backend schema changes. The generated
client is configured with an empty base URL so all requests hit the
same-origin Nginx proxy.

### Starvation Prevention

The UI visually displays the effective priority of each job. When a job
has waited longer than 1 hour beyond its `scheduled_at`, its displayed
priority improves by one level, shown as a `↑ aged → Medium` badge.

### daisyUI Styling Only

All components use daisyUI 5 class names with the `dim` theme (dark
workspace). No shadcn/ui, no MUI, no custom CSS components.
