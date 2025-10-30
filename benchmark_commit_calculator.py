#!/usr/bin/env python3
"""
Benchmark script to compare original sequential implementation
vs new parallel implementation of yearly_commit_calculator.
"""

import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from unittest.mock import MagicMock, patch
import os

# Setup paths
project_root = Path(__file__).parent

os.environ["INPUT_GH_TOKEN"] = "mock_token"
os.environ["INPUT_WAKATIME_API_KEY"] = "mock_key"
os.environ["DEBUG_RUN"] = "False"
os.environ["INPUT_IGNORED_REPOS"] = ""
os.environ["INPUT_DEBUG_LOGGING"] = "False"


class BenchmarkResult:
    def __init__(self, name: str, duration: float, repo_count: int, api_calls: int):
        self.name = name
        self.duration = duration
        self.repo_count = repo_count
        self.api_calls = api_calls

    def __str__(self):
        return (
            f"\n{self.name}:\n"
            f"  Duration: {self.duration:.3f}s\n"
            f"  Repos: {self.repo_count}\n"
            f"  API calls: {self.api_calls}\n"
            f"  Throughput: {self.repo_count/self.duration:.2f} repos/s\n"
            f"  Avg time per repo: {self.duration/self.repo_count*1000:.1f}ms"
        )


def generate_mock_data(num_repos: int = 50, branches_per_repo: int = 3, commits_per_branch: int = 20):
    """Generate mock repository data for benchmarking."""
    repos = []
    for i in range(num_repos):
        repos.append(
            {
                "name": f"repo-{i}",
                "owner": {"login": "testuser"},
                "isPrivate": i % 5 == 0,
                "primaryLanguage": {"name": ["Python", "JavaScript", "Go", "Rust", "TypeScript"][i % 5]},
            }
        )

    branches = [{"name": f"branch-{j}"} for j in range(branches_per_repo)]

    commits = []
    for k in range(commits_per_branch):
        commits.append(
            {
                "oid": f"commit-{k:04d}",
                "committedDate": f"2024-{(k % 12) + 1:02d}-{(k % 28) + 1:02d}T12:00:00Z",
                "additions": (k % 50) + 10,
                "deletions": (k % 30) + 5,
            }
        )

    return repos, branches, commits


async def benchmark_original(
    repos: List[Dict],
    branches: List[Dict],
    commits: List[Dict],
    api_latency: float = 0.01,
) -> BenchmarkResult:
    """Benchmark the original sequential implementation."""
    api_call_count = 0

    async def mock_get_remote_graphql(query, **kwargs):
        nonlocal api_call_count
        api_call_count += 1
        await asyncio.sleep(api_latency)
        return branches if "branch" in query else commits

    # Mock the managers
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

    # Patch and import
    with patch.dict(
        "sys.modules",
        {
            "manager_download": MagicMock(DownloadManager=mock_dm),
            "manager_environment": MagicMock(EnvironmentManager=mock_em),
            "manager_github": MagicMock(GitHubManager=mock_ghm),
            "manager_file": MagicMock(),
            "manager_debug": MagicMock(DebugManager=mock_dbm),
        },
    ):
        sys.path.insert(0, str(project_root / "original" / "sources"))

        if "yearly_commit_calculator" in sys.modules:
            del sys.modules["yearly_commit_calculator"]

        # Import original with patches
        from yearly_commit_calculator import calculate_commit_data

        # Run benchmark
        start = time.perf_counter()
        yearly_data, date_data = await calculate_commit_data(repos)
        duration = time.perf_counter() - start

        sys.path.remove(str(project_root / "original" / "sources"))

        return BenchmarkResult("Original (Sequential)", duration, len(repos), api_call_count)


async def benchmark_current(
    repos: List[Dict],
    branches: List[Dict],
    commits: List[Dict],
    api_latency: float = 0.01,
) -> BenchmarkResult:
    """Benchmark the current parallel implementation."""
    api_call_count = 0

    async def mock_get_remote_graphql(query, **kwargs):
        nonlocal api_call_count
        api_call_count += 1
        await asyncio.sleep(api_latency)
        return branches if "branch" in query else commits

    # Mock the managers
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
    mock_dbm.p = lambda x, **kwargs: None

    # Patch and import
    with patch.dict(
        "sys.modules",
        {
            "manager_download": MagicMock(DownloadManager=mock_dm),
            "manager_environment": MagicMock(EnvironmentManager=mock_em),
            "manager_github": MagicMock(GitHubManager=mock_ghm),
            "manager_file": MagicMock(),
            "manager_debug": MagicMock(DebugManager=mock_dbm),
        },
    ):
        sys.path.insert(0, str(project_root / "sources"))

        if "yearly_commit_calculator" in sys.modules:
            del sys.modules["yearly_commit_calculator"]

        # Import current with patches
        from yearly_commit_calculator import calculate_commit_data

        # Run benchmark
        start = time.perf_counter()
        yearly_data, date_data = await calculate_commit_data(repos)
        duration = time.perf_counter() - start

        sys.path.remove(str(project_root / "sources"))

        return BenchmarkResult("Current (Parallel with Semaphore)", duration, len(repos), api_call_count)


async def run_benchmarks():
    """Run all benchmarks with different dataset sizes."""
    print("=" * 70)
    print("Yearly Commit Calculator Benchmark")
    print("=" * 70)

    test_cases = [
        (10, 2, 10, "Small dataset (10 repos)"),
        (50, 3, 20, "Medium dataset (50 repos - typical user)"),
        (100, 3, 30, "Large dataset (100 repos)"),
        (200, 4, 40, "Extra large dataset (200 repos - power user)"),
        (500, 5, 50, "Extra large dataset (500 repos - power user)"),
        (1000, 10, 100, "Extra large dataset (1000 repos - power user)"),
    ]

    for num_repos, branches_per_repo, commits_per_branch, description in test_cases:
        print(f"\n{'=' * 70}")
        print(f"Test: {description}")
        print(f"Config: {num_repos} repos × {branches_per_repo} branches × {commits_per_branch} commits")
        print(f"Expected API calls: {num_repos * (1 + branches_per_repo)}")
        print(f"{'=' * 70}")

        repos, branches, commits = generate_mock_data(num_repos, branches_per_repo, commits_per_branch)

        # Benchmark original
        print("\n🐌 Running original implementation...")
        original_result = await benchmark_original(repos, branches, commits)
        print(original_result)

        # Benchmark current
        print("\n⚡ Running current implementation...")
        current_result = await benchmark_current(repos, branches, commits)
        print(current_result)

        # Calculate speedup
        speedup = original_result.duration / current_result.duration
        time_saved = original_result.duration - current_result.duration
        percent_saved = (1 - 1 / speedup) * 100

        print(f"\n{'─' * 70}")
        print("📊 RESULTS:")
        print(f"  ⚡ Speedup: {speedup:.2f}x faster")
        print(f"  ⏱️  Time saved: {time_saved:.2f}s ({percent_saved:.1f}%)")
        print(f"  📈 Efficiency gain: {(speedup-1)*100:.1f}% improvement")

        if speedup < 2:
            grade = "⚠️  Needs optimization"
        elif speedup < 5:
            grade = "✅ Good performance"
        elif speedup < 10:
            grade = "🎉 Excellent performance"
        else:
            grade = "🚀 Outstanding performance"

        print(f"  {grade}")
        print(f"{'─' * 70}")


async def profile_concurrency_levels():
    """Profile different concurrency levels to find optimal settings."""
    print(f"\n{'=' * 70}")
    print("Concurrency Level Profiling (100 repos)")
    print(f"{'=' * 70}\n")

    repos, branches, commits = generate_mock_data(100, 3, 30)

    concurrency_levels = [1, 2, 4, 8, 16, 32, 64]
    results = []

    print(f"{'Concurrency':>12} │ {'Duration':>10} │ {'Throughput':>15}")
    print(f"{'─'*12}─┼─{'─'*10}─┼─{'─'*15}")

    for max_concurrency in concurrency_levels:
        os.environ["INPUT_MAX_CONCURRENCY"] = str(max_concurrency)

        # Reset modules to pick up new env var
        for mod in ["yearly_commit_calculator", "manager_environment"]:
            if mod in sys.modules:
                del sys.modules[mod]

        result = await benchmark_current(repos, branches, commits, api_latency=0.01)
        results.append((max_concurrency, result.duration))

        throughput = len(repos) / result.duration
        print(f"{max_concurrency:>12} │ {result.duration:>9.3f}s │ {throughput:>10.2f} repos/s")

    best = min(results, key=lambda x: x[1])
    baseline = next(r for r in results if r[0] == 1)[1]
    speedup_vs_sequential = baseline / best[1]

    print(f"\n{'─' * 70}")
    print(f"⚡ Optimal concurrency: {best[0]} threads")
    print(f"   Duration: {best[1]:.3f}s")
    print(f"   Speedup vs sequential: {speedup_vs_sequential:.2f}x")
    print(f"{'─' * 70}")


async def simulate_real_world():
    """Simulate real-world API latency."""
    print(f"\n{'=' * 70}")
    print("Real-World Simulation (with realistic GitHub API latency)")
    print(f"{'=' * 70}\n")

    # Simulate realistic GitHub GraphQL API latency: 50-150ms
    latencies = [
        (0.05, "Fast API (50ms latency)"),
        (0.1, "Normal API (100ms latency)"),
        (0.15, "Slow API (150ms latency)"),
    ]

    repos, branches, commits = generate_mock_data(50, 3, 20)

    for latency, description in latencies:
        print(f"\n{description}:")
        print(f"{'─' * 70}")

        original_result = await benchmark_original(repos, branches, commits, api_latency=latency)
        current_result = await benchmark_current(repos, branches, commits, api_latency=latency)

        speedup = original_result.duration / current_result.duration

        print(f"  Original: {original_result.duration:.2f}s")
        print(f"  Current:  {current_result.duration:.2f}s")
        print(f"  Speedup:  {speedup:.2f}x ({original_result.duration - current_result.duration:.2f}s saved)")


async def main():
    print(f"\n🚀 Starting benchmark at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Platform: {sys.platform}\n")

    await run_benchmarks()
    await profile_concurrency_levels()
    await simulate_real_world()

    print(f"\n{'=' * 70}")
    print("✅ Benchmark completed!")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    asyncio.run(main())
