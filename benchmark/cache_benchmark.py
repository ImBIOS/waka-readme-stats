#!/usr/bin/env python3
"""
Cache Benchmark: Compare sequential API calls vs parallel with caching.

Scenario: 589 repos, only 10% change daily (~59 repos)
- Original (anmol): Sequential fetch of all 589 repos
- New: Parallel fetch of only changed repos (59) + cache reads (530)
"""

import asyncio
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from unittest.mock import MagicMock

# Setup paths
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

os.environ["INPUT_GH_TOKEN"] = "mock_token"
os.environ["INPUT_WAKATIME_API_KEY"] = "mock_key"
os.environ["DEBUG_RUN"] = "False"
os.environ["INPUT_IGNORED_REPOS"] = ""
os.environ["INPUT_DEBUG_LOGGING"] = "False"


@dataclass
class BenchmarkResult:
    name: str
    duration: float
    api_calls: int
    cache_hits: int
    repos_fetched: int
    total_repos: int

    @property
    def repos_from_cache(self) -> int:
        return self.cache_hits

    @property
    def throughput(self) -> float:
        return self.total_repos / self.duration if self.duration > 0 else 0

    def __str__(self):
        return (
            f"\n{self.name}:\n"
            f"  Duration:        {self.duration:.3f}s\n"
            f"  API calls:       {self.api_calls}\n"
            f"  Repos fetched:   {self.repos_fetched}\n"
            f"  Cache hits:      {self.cache_hits}\n"
            f"  Throughput:      {self.throughput:.2f} repos/s"
        )


def generate_repo_data(num_repos: int = 589) -> List[Dict]:
    """Generate mock repository data for 589 repos."""
    repos = []
    for i in range(num_repos):
        repos.append(
            {
                "name": f"repo-{i:03d}",
                "owner": {"login": "testuser"},
                "isPrivate": i % 5 == 0,
                "primaryLanguage": {"name": ["Python", "JavaScript", "Go", "Rust", "TypeScript"][i % 5]},
            }
        )
    return repos


def generate_commit_data(num_commits: int = 20) -> List[Dict]:
    """Generate mock commit data for a repository."""
    commits = []
    for k in range(num_commits):
        commits.append(
            {
                "oid": f"commit-{k:04d}",
                "committedDate": f"2024-{(k % 12) + 1:02d}-{(k % 28) + 1:02d}T12:00:00Z",
                "additions": (k % 50) + 10,
                "deletions": (k % 30) + 5,
            }
        )
    return commits


class CacheStore:
    """Simple in-memory cache store for benchmarking."""

    def __init__(self):
        self._cache: Dict[str, Tuple[List[Dict], float]] = {}
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[List[Dict]]:
        if key in self._cache:
            self._hits += 1
            data, timestamp = self._cache[key]
            return data
        self._misses += 1
        return None

    def set(self, key: str, data: List[Dict], timestamp: float = None):
        self._cache[key] = (data, timestamp or time.time())

    def get_stats(self) -> Tuple[int, int]:
        return self._hits, self._misses

    def clear(self):
        self._cache.clear()
        self._hits = 0
        self._misses = 0


async def benchmark_sequential_original(
    total_repos: int = 589,
    api_latency: float = 0.1,
    changed_repos_pct: float = 0.10,
) -> BenchmarkResult:
    """
    Benchmark the original sequential approach (anmol's method).

    This fetches ALL repos sequentially, regardless of whether they changed.
    """
    repos = generate_repo_data(total_repos)
    commit_data = generate_commit_data()

    api_call_count = 0

    async def mock_get_remote_graphql(query, **kwargs):
        nonlocal api_call_count
        api_call_count += 1
        await asyncio.sleep(api_latency)
        return commit_data

    # Mock managers
    mock_dm = MagicMock()
    mock_dm.get_remote_graphql = mock_get_remote_graphql

    mock_em = MagicMock()
    mock_em.IGNORED_REPOS = []
    mock_em.DEBUG_RUN = False

    mock_ghm = MagicMock()
    mock_ghm.USER = MagicMock(node_id="test_id")

    mock_dbm = MagicMock()
    mock_dbm.i = lambda x, **kwargs: None
    mock_dbm.g = lambda x, **kwargs: None
    mock_dbm.w = lambda x, **kwargs: None

    cache = CacheStore()

    # Simulate sequential fetch (like original approach)
    start = time.perf_counter()

    # Original approach: always fetch ALL repos sequentially
    for repo in repos:
        # Check if repo has changed since last fetch (simulate conditional logic)
        repo_name = repo["name"]

        # In original approach, we still make API calls for all repos
        # even if we only need to fetch changed ones
        await mock_get_remote_graphql("query { repository { ... } }")

        # Pretend we cached the result
        cache.set(repo_name, commit_data)

    duration = time.perf_counter() - start

    return BenchmarkResult(
        name="Original (Sequential - Anmol approach)",
        duration=duration,
        api_calls=api_call_count,
        cache_hits=0,  # Original doesn't use cache effectively
        repos_fetched=total_repos,
        total_repos=total_repos,
    )


async def benchmark_parallel_with_cache(
    total_repos: int = 589,
    api_latency: float = 0.1,
    changed_repos_pct: float = 0.10,
    max_concurrency: int = 10,
) -> BenchmarkResult:
    """
    Benchmark the new parallel approach with caching.

    Only fetches repos that have changed, reads others from cache.
    """
    repos = generate_repo_data(total_repos)
    commit_data = generate_commit_data()

    api_call_count = 0
    cache_hits = 0

    async def mock_get_remote_graphql(query, **kwargs):
        nonlocal api_call_count
        api_call_count += 1
        await asyncio.sleep(api_latency)
        return commit_data

    # Simulate which repos "changed" (10% of repos)
    num_changed = int(total_repos * changed_repos_pct)
    changed_repo_names = set(f"repo-{i:03d}" for i in range(num_changed))

    cache = CacheStore()

    # Pre-populate cache with "old" data for unchanged repos
    unchanged_repos = [r for r in repos if r["name"] not in changed_repo_names]
    for repo in unchanged_repos:
        cache.set(repo["name"], commit_data)

    async def fetch_repo(repo: Dict) -> Dict:
        """Fetch a single repo (simulated parallel fetch)."""
        repo_name = repo["name"]

        if repo_name in changed_repo_names:
            # Fetch from API (changed repo)
            await mock_get_remote_graphql("query { repository { ... } }")
            cache.set(repo_name, commit_data)
            return {"name": repo_name, "source": "api"}
        else:
            # Read from cache (unchanged repo)
            cached = cache.get(repo_name)
            if cached:
                nonlocal cache_hits
                cache_hits += 1
            return {"name": repo_name, "source": "cache"}

    # Parallel fetch with semaphore
    start = time.perf_counter()

    semaphore = asyncio.Semaphore(max_concurrency)

    async def fetch_with_semaphore(repo: Dict):
        async with semaphore:
            return await fetch_repo(repo)

    # Execute parallel fetches
    tasks = [fetch_with_semaphore(repo) for repo in repos]
    results = await asyncio.gather(*tasks)

    duration = time.perf_counter() - start

    return BenchmarkResult(
        name="New (Parallel + Cache)",
        duration=duration,
        api_calls=api_call_count,
        cache_hits=cache_hits,
        repos_fetched=len([r for r in results if r["source"] == "api"]),
        total_repos=total_repos,
    )


async def run_cache_benchmark():
    """Run the cache benchmark comparison."""
    print("=" * 70)
    print("CACHE BENCHMARK: Sequential vs Parallel with Caching")
    print("=" * 70)
    print("\nScenario: 589 repos, only 10% change daily (~59 repos)")
    print("Original: Fetches ALL 589 repos sequentially")
    print("New:      Fetches only 59 changed repos (parallel) + reads 530 from cache")
    print("=" * 70)

    # Test different API latency scenarios
    latency_tests = [
        (0.05, "Fast API (50ms latency)"),
        (0.1, "Normal API (100ms latency)"),
        (0.15, "Slow API (150ms latency)"),
        (0.2, "Very Slow API (200ms latency)"),
    ]

    total_repos = 589
    changed_repos = int(total_repos * 0.10)  # 10% = ~59 repos

    print(f"\nTotal repos:     {total_repos}")
    print(f"Changed repos:   {changed_repos} (10%)")
    print(f"Unchanged repos: {total_repos - changed_repos} (90% - from cache)")
    print()

    all_results = []

    for api_latency, description in latency_tests:
        print(f"\n{'─' * 70}")
        print(f"API Latency: {description}")
        print(f"{'─' * 70}")

        # Benchmark original
        print("\n[1/2] Running original (sequential)...")
        original = await benchmark_sequential_original(
            total_repos=total_repos,
            api_latency=api_latency,
            changed_repos_pct=0.10,
        )
        print(original)

        # Benchmark new with caching
        print("\n[2/2] Running new (parallel + cache)...")
        new_parallel = await benchmark_parallel_with_cache(
            total_repos=total_repos,
            api_latency=api_latency,
            changed_repos_pct=0.10,
            max_concurrency=10,
        )
        print(new_parallel)

        # Calculate improvement
        speedup = original.duration / new_parallel.duration if new_parallel.duration > 0 else 0
        time_saved = original.duration - new_parallel.duration
        api_calls_saved = original.api_calls - new_parallel.api_calls
        percent_faster = ((original.duration - new_parallel.duration) / original.duration) * 100

        print(f"\n{'=' * 70}")
        print("RESULTS:")
        print(f"  Speedup:           {speedup:.2f}x faster")
        print(f"  Time saved:        {time_saved:.2f}s ({percent_faster:.1f}% improvement)")
        print(f"  API calls saved:   {api_calls_saved} calls ({original.api_calls - new_parallel.api_calls} fewer)")
        print(f"  Throughput gain:   {original.throughput:.2f} -> {new_parallel.throughput:.2f} repos/s")

        # Grade the improvement
        if speedup < 2:
            grade = "Needs optimization"
        elif speedup < 5:
            grade = "Good improvement"
        elif speedup < 10:
            grade = "Excellent improvement"
        else:
            grade = "Outstanding improvement"

        print(f"  Rating:            {grade}")
        print(f"{'=' * 70}")

        all_results.append(
            {
                "latency": description,
                "original": original,
                "new": new_parallel,
                "speedup": speedup,
            }
        )

    # Summary table
    print("\n" + "=" * 70)
    print("SUMMARY TABLE")
    print("=" * 70)
    print(f"{'API Latency':<25} | {'Original':>12} | {'New':>12} | {'Speedup':>10}")
    print(f"{'-' * 25}-+-{'-' * 12}-+-{'-' * 12}-+-{'-' * 10}")

    for result in all_results:
        latency = result["latency"].split(" (")[0]  # Shorten
        orig = f"{result['original'].duration:.2f}s"
        new = f"{result['new'].duration:.2f}s"
        speedup = f"{result['speedup']:.2f}x"
        print(f"{latency:<25} | {orig:>12} | {new:>12} | {speedup:>10}")

    print("=" * 70)

    # API call comparison
    print("\nAPI CALL COMPARISON:")
    print("-" * 70)
    orig_calls = all_results[0]["original"].api_calls
    new_calls = all_results[0]["new"].api_calls
    reduction = orig_calls - new_calls
    reduction_pct = (reduction / orig_calls) * 100
    print(f"Original approach:  {orig_calls} API calls per run")
    print(f"New approach:       {new_calls} API calls per run")
    print(f"Reduction:          {reduction} fewer calls ({reduction_pct:.1f}% reduction)")
    print("-" * 70)

    return all_results


async def profile_concurrency_levels():
    """Profile different concurrency levels for the parallel approach."""
    print("\n" + "=" * 70)
    print("CONCURRENCY LEVEL PROFILING")
    print("=" * 70)
    print("Testing different concurrency levels with cache optimization...")
    print()

    total_repos = 589
    api_latency = 0.1  # 100ms typical

    concurrency_levels = [1, 2, 4, 6, 8, 10, 15, 20]
    results = []

    print(f"{'Concurrency':>12} | {'Duration':>10} | {'Throughput':>15} | {'Speedup vs Seq':>15}")
    print(f"{'-' * 12}-+-{'-' * 10}-+-{'-' * 15}-+-{'-' * 15}")

    for concurrency in concurrency_levels:
        result = await benchmark_parallel_with_cache(
            total_repos=total_repos,
            api_latency=api_latency,
            changed_repos_pct=0.10,
            max_concurrency=concurrency,
        )
        results.append((concurrency, result.duration, result.throughput))

        throughput = result.throughput
        baseline_throughput = total_repos / (total_repos * api_latency)
        speedup_ratio = throughput / baseline_throughput if baseline_throughput > 0 else 0
        print(f"{concurrency:>12} | {result.duration:>9.3f}s | {throughput:>10.2f} repos/s | {speedup_ratio:>15.2f}x")

    best = min(results, key=lambda x: x[1])

    # Calculate speedup vs sequential (589 repos × 100ms × sequential = 58.9s)
    sequential_baseline = total_repos * api_latency  # ~58.9s
    speedup_vs_sequential = sequential_baseline / best[1]

    print("\n" + "-" * 70)
    print(f"Optimal concurrency: {best[0]} threads")
    print(f"Duration:            {best[1]:.3f}s")
    print(f"Speedup vs sequential: {speedup_vs_sequential:.2f}x")
    print("-" * 70)


async def main():
    print("\n" + "=" * 70)
    print("CACHE BENCHMARK")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python:  {sys.version.split()[0]}")
    print("=" * 70 + "\n")

    await run_cache_benchmark()
    await profile_concurrency_levels()

    print("\n" + "=" * 70)
    print("BENCHMARK COMPLETED!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
