"""Seed script — populate the job scheduler with realistic test jobs.

Creates a representative workload to exercise:
- Concurrency (many concurrent jobs across all priorities)
- DAG workflows (3-step pipeline: report → upload → email)
- Scheduled future jobs
- Recurring jobs
- Deliberate failures (bad payloads → retries → DLQ)
- DLQ threshold trigger (≥ 10 failed jobs → email alert)

Usage:
    cd backend
    uv run python ../scripts/seed_jobs.py                    # hit localhost:8000
    uv run python ../scripts/seed_jobs.py http://<host>:8000 # remote server
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta, timezone

import httpx

# ── Config ────────────────────────────────────────────────────────────────

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
API = f"{BASE_URL}/api/v1"

# How many seconds to wait between batches (let the worker process them)
PAUSE = 2


# ── Helpers ───────────────────────────────────────────────────────────────


def post_job(data: dict, label: str = "") -> str | None:
    """POST a single job. Returns the job UUID on success, None on failure."""
    try:
        r = httpx.post(f"{API}/jobs", json=data, timeout=10)
        r.raise_for_status()
        job = r.json()
        jid = job["id"][:8]
        print(f"  ✓  {label:30s} → {jid}  [{job['type']}] p{job['priority']}")
        return job["id"]
    except httpx.HTTPError as exc:
        print(
            f"  ✗  {label:30s} → {exc.response.status_code if hasattr(exc, 'response') else exc}"
        )
        return None


def ts(offset_seconds: int = 0) -> str:
    """ISO-8601 timestamp relative to now."""
    return (datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)).isoformat()


def main() -> None:
    print(f"\n{'=' * 60}")
    print(f"  Seeding jobs → {API}/jobs")
    print(f"{'=' * 60}\n")

    dag_ids: dict[str, str] = {}

    # ────────────────────────────────────────────────────────────────────
    # 1. High-priority burst — test concurrency (all three handlers)
    # ────────────────────────────────────────────────────────────────────
    print("───── 1. Concurrency burst (6 jobs, mixed priorities) ─────")
    for i in range(6):
        p = 1 if i < 2 else 2 if i < 4 else 3
        htype = ["send_email", "webhook", "log_processing"][i % 3]
        post_job(
            {
                "type": htype,
                "priority": p,
                "payload": {"batch": "concurrency", "index": i, "ts": time.time()},
            },
            f"Burst #{i + 1}",
        )
        time.sleep(0.3)
    time.sleep(PAUSE)

    # ────────────────────────────────────────────────────────────────────
    # 2. DAG workflow — 3-step pipeline (report → upload → email)
    # ────────────────────────────────────────────────────────────────────
    print("\n───── 2. DAG workflow (3-step pipeline) ─────")
    report_id = post_job(
        {
            "type": "log_processing",
            "priority": 1,
            "payload": {"lines": 8192, "step": "generate_report"},
        },
        "Step 1 — Generate Report",
    )
    time.sleep(0.5)

    upload_id = None
    if report_id:
        upload_id = post_job(
            {
                "type": "webhook",
                "priority": 1,
                "payload": {
                    "url": "https://hooks.dilamme.io/upload",
                    "step": "upload_file",
                },
                "dependency_ids": [report_id],
            },
            "Step 2 — Upload File",
        )
    time.sleep(0.5)

    if upload_id:
        dag_ids["report"] = report_id or ""
        dag_ids["upload"] = upload_id
        dag_ids["email"] = (
            post_job(
                {
                    "type": "send_email",
                    "priority": 1,
                    "payload": {
                        "to": "ops@dilamme.io",
                        "subject": "Report ready",
                        "step": "send_email",
                    },
                    "dependency_ids": [upload_id],
                },
                "Step 3 — Send Email",
            )
            or ""
        )
        dag_ids["email"] = dag_ids["email"] or ""
    time.sleep(PAUSE)

    # ────────────────────────────────────────────────────────────────────
    # 3. Scheduled future jobs
    # ────────────────────────────────────────────────────────────────────
    print("\n───── 3. Scheduled future jobs ─────")
    for offset in [30, 60, 120, 300]:
        post_job(
            {
                "type": "send_email",
                "priority": 2,
                "payload": {
                    "to": "future@dilamme.com",
                    "subject": f"Deferred +{offset}s",
                },
                "scheduled_at": ts(offset),
            },
            f"Deferred +{offset}s",
        )
    time.sleep(0.5)

    # ────────────────────────────────────────────────────────────────────
    # 4. Recurring jobs
    # ────────────────────────────────────────────────────────────────────
    print("\n───── 4. Recurring jobs ─────")
    post_job(
        {
            "type": "log_processing",
            "priority": 3,
            "payload": {"lines": 512, "label": "heartbeat"},
            "interval": "every_1_minute",
        },
        "Recurring — every 1 min",
    )
    time.sleep(0.5)

    # ────────────────────────────────────────────────────────────────────
    # 5. Failing jobs — empty payload, bad email, etc. → retries → DLQ
    # ────────────────────────────────────────────────────────────────────
    print("\n───── 5. Deliberate failures (retries → DLQ) ─────")
    failure_payloads = [
        {"type": "send_email", "payload": {}},  # missing 'to'
        {
            "type": "send_email",
            "payload": {"to": "not-an-email", "subject": "X"},
        },  # invalid email
        {
            "type": "send_email",
            "payload": {"to": "bad@x", "subject": ""},
        },  # empty subject
        {"type": "webhook", "payload": {}},  # missing 'url'
        {"type": "webhook", "payload": {"url": ""}},  # empty url
        {"type": "log_processing", "payload": {}},  # missing 'lines'
        # Add a few more to push past the DLQ threshold of 10
        {
            "type": "send_email",
            "payload": {"to": "x@y", "subject": "bad-1"},
        },  # mock failure rate 10%
        {"type": "send_email", "payload": {"to": "x@y", "subject": "bad-2"}},
        {"type": "send_email", "payload": {"to": "x@y", "subject": "bad-3"}},
        {"type": "send_email", "payload": {"to": "x@y", "subject": "bad-4"}},
        {"type": "webhook", "payload": {"url": "https://evil.local/fail"}},
    ]

    for i, fp in enumerate(failure_payloads):
        post_job(
            {
                "type": fp["type"],
                "priority": 1,  # high priority so they run quickly
                "payload": fp["payload"],
            },
            f"Fail #{i + 1} — {fp['type']}",
        )
        time.sleep(0.3)

    time.sleep(PAUSE)

    # ────────────────────────────────────────────────────────────────────
    # Summary
    # ────────────────────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("  Seeding complete.")
    print(f"{'=' * 60}")
    print(f"\n  Dashboard:  {BASE_URL}/docs")
    print(
        f"  Frontend:   {BASE_URL.replace(':8000', ':5173') if 'localhost' in BASE_URL else BASE_URL}\n"
    )
    print("  DAG workflow IDs:")
    for step, jid in dag_ids.items():
        print(f"    {step:10s} → {jid}")
    print()


if __name__ == "__main__":
    # Ensure httpx is available
    try:
        import httpx  # noqa: F401
    except ImportError:
        print("httpx is required: uv run pip install httpx")
        sys.exit(1)

    main()
