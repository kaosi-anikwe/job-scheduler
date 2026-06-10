"""Benchmark harness — heap vs. timing wheel performance comparison.

Measures insert and extract times at various scales (100, 1K, 10K, 100K jobs)
and outputs a markdown comparison table.

Run with: ``uv run --package worker python -m worker.scheduler.benchmark``
"""

from __future__ import annotations

import asyncio
import random
import time
from typing import Any

from worker.scheduler.heap_scheduler import HeapScheduler, JobNode
from worker.scheduler.timing_wheel import HashedTimingWheel, TimingWheelJob


def _generate_jobs(n: int) -> list[dict[str, Any]]:
    """Generate N synthetic job specifications."""
    now = time.time()
    jobs: list[dict[str, Any]] = []
    for i in range(n):
        jobs.append(
            {
                "job_id": f"bench-{i}",
                "job_type": "send_email",
                "base_priority": random.choice([1, 2, 3]),
                "scheduled_at": now + random.uniform(0, 3600),
                "created_at": now - random.uniform(0, 7200),
                "payload": {"index": i},
            }
        )
    return jobs


async def _benchmark_heap(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    """Benchmark the HeapScheduler: insert all, then extract all."""
    heap = HeapScheduler()

    # -- Insert --
    insert_times: list[float] = []
    for spec in jobs:
        node = JobNode(**spec)
        start = time.perf_counter()
        await heap.push(node)
        insert_times.append(time.perf_counter() - start)

    # -- Extract --
    extract_times: list[float] = []
    while True:
        start = time.perf_counter()
        popped = await heap.pop()
        elapsed = time.perf_counter() - start
        if popped is None:
            break
        extract_times.append(elapsed)

    return {
        "insert": insert_times,
        "extract": extract_times,
    }


async def _benchmark_timing_wheel(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    """Benchmark the HashedTimingWheel: insert all, then tick through all."""
    wheel = HashedTimingWheel(num_slots=60, tick_duration=1.0)

    # -- Insert --
    insert_times: list[float] = []
    for spec in jobs:
        tw_job = TimingWheelJob(
            job_id=spec["job_id"],
            job_type=spec["job_type"],
            scheduled_at=spec["scheduled_at"],
            payload=spec["payload"],
        )
        start = time.perf_counter()
        await wheel.add_job(tw_job)
        insert_times.append(time.perf_counter() - start)

    # -- Extract (tick through all slots × rounds) --
    extract_times: list[float] = []
    max_ticks = 60 * 100  # Upper bound to prevent infinite loop
    for _ in range(max_ticks):
        start = time.perf_counter()
        ready = await wheel.tick()
        elapsed = time.perf_counter() - start
        if ready:
            extract_times.append(elapsed)
        remaining = await wheel.size()
        if remaining == 0:
            break

    return {
        "insert": insert_times,
        "extract": extract_times,
    }


def _percentile(data: list[float], p: int) -> float:
    """Calculate the p-th percentile of a list of floats."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * p / 100
    f = int(k)
    c = f + 1
    if c >= len(sorted_data):
        return sorted_data[f]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


def _format_us(seconds: float) -> str:
    """Format seconds as microseconds string."""
    return f"{seconds * 1_000_000:.2f}µs"


async def run_benchmarks() -> str:
    """Run all benchmarks and return a markdown report."""
    sizes = [100, 1_000, 10_000, 100_000]
    lines: list[str] = []

    lines.append("# Scheduler Benchmark: Heap vs. Timing Wheel\n")
    lines.append(f"Generated at: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n")

    lines.append("## Insert Performance\n")
    lines.append("| Jobs | Algo | p50 | p95 | p99 | Total |")
    lines.append("|------|------|-----|-----|-----|-------|")

    for n in sizes:
        jobs = _generate_jobs(n)

        heap_result = await _benchmark_heap(jobs)
        wheel_result = await _benchmark_timing_wheel(jobs)

        for name, result in [("Heap", heap_result), ("Wheel", wheel_result)]:
            ins = result["insert"]
            lines.append(
                f"| {n:,} | {name} "
                f"| {_format_us(_percentile(ins, 50))} "
                f"| {_format_us(_percentile(ins, 95))} "
                f"| {_format_us(_percentile(ins, 99))} "
                f"| {sum(ins) * 1000:.2f}ms |"
            )

    lines.append("\n## Extract Performance\n")
    lines.append("| Jobs | Algo | p50 | p95 | p99 | Total |")
    lines.append("|------|------|-----|-----|-----|-------|")

    for n in sizes:
        jobs = _generate_jobs(n)

        heap_result = await _benchmark_heap(jobs)
        wheel_result = await _benchmark_timing_wheel(jobs)

        for name, result in [("Heap", heap_result), ("Wheel", wheel_result)]:
            ext = result["extract"]
            if ext:
                lines.append(
                    f"| {n:,} | {name} "
                    f"| {_format_us(_percentile(ext, 50))} "
                    f"| {_format_us(_percentile(ext, 95))} "
                    f"| {_format_us(_percentile(ext, 99))} "
                    f"| {sum(ext) * 1000:.2f}ms |"
                )
            else:
                lines.append(f"| {n:,} | {name} | N/A | N/A | N/A | N/A |")

    lines.append("\n## Analysis\n")
    lines.append("### Heap (Min-Heap Priority Queue)")
    lines.append("- **Insert:** O(log n) — maintains heap invariant on push")
    lines.append("- **Extract-min:** O(log n) — re-heapify on pop")
    lines.append("- **Priority ordering:** Native — jobs extracted in exact priority order")
    lines.append("- **Best for:** Workloads with mixed priorities requiring strict ordering\n")
    lines.append("### Hashed Timing Wheel")
    lines.append("- **Insert:** O(1) — direct slot assignment via modular arithmetic")
    lines.append("- **Tick:** O(k) where k = jobs in current slot — no global reordering")
    lines.append("- **Priority ordering:** None within a slot (FIFO)")
    lines.append("- **Best for:** High-volume delayed/scheduled jobs with uniform timing\n")
    lines.append("### Tradeoff Summary")
    lines.append("The heap excels when priority ordering is critical and job volumes are moderate.")
    lines.append(
        "The timing wheel excels at high-volume scheduled events where O(1) insert matters"
    )
    lines.append("more than per-job priority ordering.")

    return "\n".join(lines)


async def main() -> None:
    """Run benchmarks and print/save results."""
    report = await run_benchmarks()
    print(report)

    # Also save to file
    with open("benchmark_results.md", "w") as f:
        f.write(report)
    print("\nResults saved to benchmark_results.md")


if __name__ == "__main__":
    asyncio.run(main())
