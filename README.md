# Background Job Scheduler

Production-grade background job scheduler with heap-based priority queue, DAG workflows, distributed locking, and real-time WebSocket updates.

## Monorepo Structure

```
job-scheduler/
├── backend/           # Python backend (uv workspace)
│   ├── packages/
│   │   ├── shared/    # Models, schemas, config, DB/Redis
│   │   ├── api/       # FastAPI HTTP + WebSocket server
│   │   └── worker/    # Scheduler, executor, handlers
│   ├── alembic/       # Database migrations
│   └── pyproject.toml # uv workspace root
├── frontend/          # React dashboard UI
└── deploy/            # Nginx, systemd, deployment scripts
```

## Tech Stack

| Layer           | Technology              |
| --------------- | ----------------------- |
| API Framework   | FastAPI                 |
| ORM             | SQLAlchemy 2.0 (async)  |
| Database        | PostgreSQL              |
| Cache / Pub-Sub | Redis                   |
| Package Manager | uv                      |
| Reverse Proxy   | Nginx                   |
| Frontend        | React 18 + TypeScript 5 |
| Styling         | daisyUI 5 (Tailwind 4)  |
| API Client      | hey-api (OpenAPI gen)   |
| Real-Time       | WebSocket               |

## Getting Started

```bash
# Backend
cd backend
uv sync --all-packages
cp .env.example .env  # edit with your DB/Redis credentials

# Run migrations
uv run alembic upgrade head

# Start API server
uv run --package api uvicorn api.main:app --reload --port 8000

# Start worker (separate terminal)
uv run --package worker python -m worker.main

# Frontend
cd frontend
npm install
npm run generate-api   # Generate the hey-api SDK from the running backend
npm run dev            # Starts Vite dev server on :5173, proxies /api → :8000
```

## API Documentation

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **OpenAPI JSON:** http://localhost:8000/openapi.json
