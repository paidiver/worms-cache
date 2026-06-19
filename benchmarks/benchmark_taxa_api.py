"""
Benchmark: Django (Python) vs Rust Axum REST API
=================================================

Measures wall-clock latency for identical requests sent to both services and
prints a concise comparison table.

Usage
-----
# With both services running locally (adjust URLs / ports as needed):
    python benchmarks/benchmark_taxa_api.py

Environment variables (all optional, defaults shown):
    DJANGO_BASE_URL   http://localhost:8001   Base URL of the Django service
    RUST_BASE_URL     http://localhost:8002   Base URL of the Rust service
    CONCURRENCY       10                      Number of parallel workers
    REPEATS           5                       Repetitions per scenario
    APHIA_IDS         comma-separated list    AphiaIDs to use in benchmark
                      (falls back to the ids in initial_aphia_ids.txt)
"""

from __future__ import annotations

import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, NamedTuple

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DJANGO_BASE = os.environ.get("DJANGO_BASE_URL", "http://localhost:8001/api").rstrip("/")
RUST_BASE = os.environ.get("RUST_BASE_URL", "http://localhost:8002").rstrip("/")
CONCURRENCY = int(os.environ.get("CONCURRENCY", 10))
REPEATS = int(os.environ.get("REPEATS", 5))

_DEFAULT_IDS_FILE = Path(__file__).parent.parent / "initial_aphia_ids.txt"
_env_ids = os.environ.get("APHIA_IDS", "")
if _env_ids:
    APHIA_IDS: list[int] = [int(x.strip()) for x in _env_ids.split(",") if x.strip()]
elif _DEFAULT_IDS_FILE.exists():
    APHIA_IDS = [int(ln.strip()) for ln in _DEFAULT_IDS_FILE.read_text().splitlines() if ln.strip()]
else:
    APHIA_IDS = [146419, 1828, 152352, 10194, 843664]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class Timing(NamedTuple):
    mean_ms: float
    median_ms: float
    p95_ms: float
    min_ms: float
    max_ms: float
    errors: int
    total_requests: int


def _timed_get(url: str, params: dict | None = None, session: requests.Session | None = None) -> float | None:
    """Return elapsed milliseconds for a single GET, or None on error."""
    client = session or requests
    try:
        t0 = time.perf_counter()
        resp = client.get(url, params=params, timeout=30)
        elapsed = (time.perf_counter() - t0) * 1000
        resp.raise_for_status()
        return elapsed

    except requests.HTTPError as exc:
        response = exc.response
        body = response.text[:500] if response is not None else ""
        print(
            f"HTTP error: {url} params={params} -> {exc}\nResponse body: {body}",
            file=sys.stderr,
        )
        return None

    except requests.RequestException as exc:
        print(f"Request error: {url} params={params} -> {exc}", file=sys.stderr)
        return None

    except Exception as exc:
        print(f"Unexpected error: {url} params={params} -> {exc}", file=sys.stderr)
        return None


def _run_scenario(
    label: str,
    request_fn: Callable[[], float | None],
    total: int,
    concurrency: int,
) -> Timing:
    """Execute *total* calls with *concurrency* workers and return aggregated stats."""
    samples: list[float] = []
    errors = 0

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(request_fn) for _ in range(total)]
        for fut in as_completed(futures):
            result = fut.result()
            if result is None:
                errors += 1
            else:
                samples.append(result)

    if not samples:
        return Timing(float("inf"), float("inf"), float("inf"), float("inf"), float("inf"), errors, total)

    samples.sort()
    p95_idx = max(0, int(len(samples) * 0.95) - 1)
    return Timing(
        mean_ms=statistics.mean(samples),
        median_ms=statistics.median(samples),
        p95_ms=samples[p95_idx],
        min_ms=samples[0],
        max_ms=samples[-1],
        errors=errors,
        total_requests=total,
    )


# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------


def _build_scenarios() -> list[tuple[str, str, str, dict | None]]:
    """
    Each entry: (scenario_label, django_url, rust_url, query_params)
    """
    ids_param = {"aphia_ids[]": APHIA_IDS}
    first_id = APHIA_IDS[0]

    return [
        # (
        #     "GET /taxa/  (list, no filter)",
        #     f"{DJANGO_BASE}/taxa/",
        #     f"{RUST_BASE}/taxa/",
        #     None,
        # ),
        # (
        #     f"GET /taxa/{first_id}/  (single fetch)",
        #     f"{DJANGO_BASE}/taxa/{first_id}/",
        #     f"{RUST_BASE}/taxa/{first_id}/",
        #     None,
        # ),
        # (
        #     f"GET /taxa/{first_id}/ + parents + descendants",
        #     f"{DJANGO_BASE}/taxa/{first_id}/",
        #     f"{RUST_BASE}/taxa/{first_id}/",
        #     {"include_parents": "true", "include_descendants": "true"},
        # ),
        (
            "GET /taxa/ids_with_descendants/ (batch)",
            f"{DJANGO_BASE}/taxa/ids_with_descendants/",
            f"{RUST_BASE}/taxa/ids_with_descendants/",
            ids_param,
        ),
        # (
        #     f"GET /taxa/synonyms/{first_id}/",
        #     f"{DJANGO_BASE}/taxa/synonyms/{first_id}/",
        #     f"{RUST_BASE}/taxa/synonyms/{first_id}/",
        #     None,
        # ),
        # (
        #     f"GET /taxa/classification/{first_id}/",
        #     f"{DJANGO_BASE}/taxa/classification/{first_id}/",
        #     f"{RUST_BASE}/taxa/classification/{first_id}/",
        #     None,
        # ),
        # (
        #     "GET /taxa/ajax_by_name_part/Acacia",
        #     f"{DJANGO_BASE}/taxa/ajax_by_name_part/Acacia",
        #     f"{RUST_BASE}/taxa/ajax_by_name_part/Acacia",
        #     None,
        # ),
        # (
        #     "GET /taxa/match_names/  (3 names)",
        #     f"{DJANGO_BASE}/taxa/match_names/",
        #     f"{RUST_BASE}/taxa/match_names/",
        #     {"scientificnames[]": ["Acacia", "Homo sapiens", "Gadus morhua"]},
        # ),
        # (
        #     "GET /ranks/  (list)",
        #     f"{DJANGO_BASE}/ranks/",
        #     f"{RUST_BASE}/ranks/",
        #     None,
        # ),
        # (
        #     "GET /vernaculars/  (list, no filter)",
        #     f"{DJANGO_BASE}/vernaculars/",
        #     f"{RUST_BASE}/vernaculars/",
        #     None,
        # ),
    ]


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

_COL = {
    "scenario": 52,
    "service": 8,
    "mean": 9,
    "median": 9,
    "p95": 9,
    "min": 9,
    "max": 9,
    "err": 6,
}


def _header() -> str:
    return (
        f"{'Scenario':<{_COL['scenario']}}"
        f"{'Service':<{_COL['service']}}"
        f"{'Mean ms':>{_COL['mean']}}"
        f"{'Median ms':>{_COL['median']}}"
        f"{'p95 ms':>{_COL['p95']}}"
        f"{'Min ms':>{_COL['min']}}"
        f"{'Max ms':>{_COL['max']}}"
        f"{'Errors':>{_COL['err']}}"
    )


def _row(scenario: str, service: str, t: Timing) -> str:
    return (
        f"{scenario:<{_COL['scenario']}}"
        f"{service:<{_COL['service']}}"
        f"{t.mean_ms:>{_COL['mean']}.1f}"
        f"{t.median_ms:>{_COL['median']}.1f}"
        f"{t.p95_ms:>{_COL['p95']}.1f}"
        f"{t.min_ms:>{_COL['min']}.1f}"
        f"{t.max_ms:>{_COL['max']}.1f}"
        f"{t.errors:>{_COL['err']}}"
    )


def _speedup(django: Timing, rust: Timing) -> str:
    if rust.mean_ms == 0 or rust.mean_ms == float("inf"):
        return "N/A"
    ratio = django.mean_ms / rust.mean_ms
    arrow = "faster" if ratio >= 1 else "slower"
    return f"  → Rust is {abs(ratio):.2f}× {arrow} (mean)"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _check_service(base_url: str, name: str) -> bool:
    try:
        r = requests.get(f"{base_url}/health/", timeout=5)
        r.raise_for_status()
        print(f"  {name:8s}  {base_url}  [OK]")
        return True
    except Exception as exc:
        print(f"  {name:8s}  {base_url}  [UNREACHABLE: {exc}]")
        return False


def main() -> None:
    total_requests = REPEATS * CONCURRENCY

    print("=" * 90)
    print("  worms-cache  API Benchmark  —  Django vs Rust/Axum")
    print("=" * 90)
    print(f"  Concurrency : {CONCURRENCY} workers")
    print(f"  Repeats     : {REPEATS}  (total per scenario = {total_requests})")
    print(f"  AphiaIDs    : {APHIA_IDS}")
    print()
    print("Checking services …")
    django_ok = _check_service(DJANGO_BASE, "Django")
    rust_ok = _check_service(RUST_BASE, "Rust")
    print()

    if not django_ok and not rust_ok:
        print("Both services unreachable — aborting.", file=sys.stderr)
        sys.exit(1)

    sep = "-" * (sum(_COL.values()))
    print(_header())
    print(sep)

    session_django = requests.Session()
    session_rust = requests.Session()

    for scenario_label, django_url, rust_url, params in _build_scenarios():
        results: dict[str, Timing] = {}

        if django_ok:
            django_timing = _run_scenario(
                label=scenario_label,
                request_fn=lambda u=django_url, p=params: _timed_get(u, p, session_django),
                total=total_requests,
                concurrency=CONCURRENCY,
            )
            results["Django"] = django_timing
            print(_row(scenario_label, "Django", django_timing))

        if rust_ok:
            rust_timing = _run_scenario(
                label=scenario_label,
                request_fn=lambda u=rust_url, p=params: _timed_get(u, p, session_rust),
                total=total_requests,
                concurrency=CONCURRENCY,
            )
            results["Rust"] = rust_timing
            print(_row("", "Rust", rust_timing))

        if "Django" in results and "Rust" in results:
            print(" " * (_COL["scenario"] + _COL["service"]) + _speedup(results["Django"], results["Rust"]))

        print(sep)

    print()
    print("Done.")


if __name__ == "__main__":
    main()
