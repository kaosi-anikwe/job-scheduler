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

## Production Deployment

Assumes a **fresh Ubuntu 24.04 LTS** instance. Adjust paths and hostnames
as needed.

### 1. System Dependencies

```bash
sudo apt update && sudo apt install -y \
    postgresql postgresql-contrib \
    redis-server \
    nginx \
    certbot python3-certbot-nginx

# Ensure services are running
sudo systemctl enable --now postgresql redis-server nginx
```

### 2. Database Setup

```bash
sudo -u postgres psql <<SQL
CREATE DATABASE job_scheduler;
CREATE USER ubuntu WITH PASSWORD 'your-password-here';
GRANT ALL PRIVILEGES ON DATABASE job_scheduler TO ubuntu;
GRANT CREATE ON SCHEMA public TO ubuntu;
ALTER DATABASE job_scheduler OWNER TO ubuntu;
SQL
```

### 3. Clone & Configure

```bash
git clone https://github.com/kaosi-anikwe/job-scheduler.git /opt/dilamme-scheduler
cd /opt/dilamme-scheduler

# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Backend
cd backend
uv sync --all-packages
cp .env.example .env
# Edit .env — set DATABASE_URL, REDIS_URL with real credentials
nano .env

# Run initial migration
uv run alembic upgrade head

# Frontend
cd ../frontend
npm install
npm run build   # builds to frontend/dist/
```

### 4. Systemd Services

```bash
cd /opt/dilamme-scheduler/deploy/systemd

# Copy units into place
sudo cp api.service worker.service /etc/systemd/system/

# Reload and enable
sudo systemctl daemon-reload
sudo systemctl enable --now api.service worker.service

# Verify
sudo systemctl status api worker
```

### 5. Nginx (Reverse Proxy + HTTPS)

```bash
# Copy the site config
sudo cp /opt/dilamme-scheduler/deploy/nginx.conf /etc/nginx/sites-available/dilamme
sudo ln -s /etc/nginx/sites-available/dilamme /etc/nginx/sites-enabled/

# Edit the server_name to match your domain
sudo nano /etc/nginx/sites-available/dilamme

# Test and reload
sudo nginx -t
sudo systemctl reload nginx

# HTTPS via Let's Encrypt
sudo certbot --nginx -d scheduler.yourdomain.com
```

### 6. Firewall

```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP  (redirects to HTTPS)
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

### 7. Verify

```bash
# API health check
curl https://scheduler.yourdomain.com/api/v1/health | jq
# → {"status":"ok","database":"ok","redis":"ok"}

# Swagger UI
open https://scheduler.yourdomain.com/docs

# Frontend dashboard
open https://scheduler.yourdomain.com
```

### 8. Managing

```bash
# View live logs
sudo journalctl -u api -f
sudo journalctl -u worker -f

# Restart after pulling changes
cd /opt/dilamme-scheduler && git pull
sudo systemctl restart api worker

# Rebuild frontend after pull
cd /opt/dilamme-scheduler/frontend && npm install && npm run build
```

### Environment Variables

All configuration lives in `/opt/dilamme-scheduler/backend/.env`:

| Variable              | Default                  | Description                        |
| --------------------- | ------------------------ | ---------------------------------- |
| `DATABASE_URL`        | (required)               | PostgreSQL connection string       |
| `REDIS_URL`           | `redis://localhost:6379` | Redis connection string            |
| `WORKER_CONCURRENCY`  | `4`                      | Number of worker tasks             |
| `SCHEDULER_ENGINE`    | `heap`                   | `heap` or `timing_wheel`           |
| `DLQ_ALERT_THRESHOLD` | `10`                     | DLQ size that triggers email alert |
| `DLQ_ALERT_EMAIL`     | (required)               | Where DLQ alerts are sent          |
| `LOG_LEVEL`           | `INFO`                   | Log level for all components       |
