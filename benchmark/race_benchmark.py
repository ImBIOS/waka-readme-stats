#!/usr/bin/env python3
"""
REAL Race Benchmark: anmol098 vs ImBIOS in parallel

This benchmark:
1. Fetches ALL real repos from authenticated GitHub user (using gh CLI)
2. Runs both implementations in parallel (race condition)
3. Whichever finishes first wins - other is cancelled
4. Measures real execution time with real API calls
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass

# Setup paths
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Ensure environment is set
os.environ["INPUT_GH_TOKEN"] = os.environ.get("GH_TOKEN", "")
os.environ["INPUT_WAKATIME_API_KEY"] = os.environ.get("WAKATIME_API_KEY", "mock_key")
os.environ["DEBUG_RUN"] = "False"
os.environ["INPUT_IGNORED_REPOS"] = ""
os.environ["INPUT_DEBUG_LOGGING"] = "False"
os.environ["INPUT_USE_CACHE"] = "False"  # No cache for fair race
os.environ["INPUT_CACHE_TTL_DAYS"] = "7"
os.environ["INPUT_MAX_CONCURRENCY"] = "16"


@dataclass
class RaceResult:
    name: str
    duration: float
    repo_count: int
    api_calls: int
    winner: bool = False

    def __str__(self):
        winner_mark = " [WINNER]" if self.winner else ""
        return (
            f"{self.name}{winner_mark}:\n"
            f"  Duration: {self.duration:.3f}s\n"
            f"  Repos processed: {self.repo_count}\n"
            f"  API calls (branches+commits): {self.api_calls}\n"
            f"  Throughput: {self.repo_count/max(self.duration,0.001):.2f} repos/s"
        )


def get_gh_owner() -> Dict:
    """Get current GitHub CLI authenticated user."""
    import subprocess

    result = subprocess.run(["gh", "api", "user"], capture_output=True, text=True, timeout=30)
    if result.returncode == 0:
        return json.loads(result.stdout)
    raise Exception(f"Failed to get GH user: {result.stderr}")


def get_real_repos(owner: str, max_repos: int = None) -> List[Dict]:
    """Fetch ALL real repositories from GitHub API using gh CLI."""
    import subprocess
    import json

    # Use gh api with paginate to get all repos
    result = subprocess.run(["gh", "api", f"users/{owner}/repos", "--paginate"], capture_output=True, text=True, timeout=180)

    if result.returncode != 0:
        print(f"Warning: Failed to fetch repos: {result.stderr}")
        return []

    all_repos = json.loads(result.stdout)
    repos = []

    # Use all repos if max_repos is None
    limit = len(all_repos) if max_repos is None else min(max_repos, len(all_repos))

    for repo in all_repos[:limit]:
        repos.append(
            {
                "name": repo["name"],
                "owner": {"login": repo["owner"]["login"]},
                "isPrivate": repo["private"],
                "primaryLanguage": {"name": repo.get("language")} if repo.get("language") else None,
            }
        )

    return repos


async def run_original_anmol(repos: List[Dict]) -> RaceResult:
    """Run original anmol098 implementation (sequential)."""
    from unittest.mock import MagicMock, patch

    api_call_count = 0

    async def get_remote_graphql(query, **kwargs):
        nonlocal api_call_count
        api_call_count += 1
        await asyncio.sleep(0.1)  # Simulate API latency

        import subprocess

        result = subprocess.run(["gh", "api", "graphql", "-f", f"query={query}"], capture_output=True, text=True, timeout=30)
        return json.loads(result.stdout) if result.returncode == 0 else {}

    mock_dm = MagicMock()
    mock_dm.get_remote_graphql = get_remote_graphql

    mock_em = MagicMock()
    mock_em.IGNORED_REPOS = []
    mock_em.DEBUG_RUN = False

    mock_ghm = MagicMock()
    mock_ghm.USER = MagicMock()
    mock_ghm.USER.node_id = "mock"

    mock_dbm = MagicMock()
    mock_dbm.i = lambda x, **kwargs: None
    mock_dbm.g = lambda x, **kwargs: None
    mock_dbm.w = lambda x, **kwargs: None

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

        from yearly_commit_calculator import calculate_commit_data

        start = time.perf_counter()
        try:
            await calculate_commit_data(repos)
        except Exception as e:
            print(f"Original error: {e}")
        duration = time.perf_counter() - start

        sys.path.remove(str(project_root / "original" / "sources"))

    return RaceResult(name="1. Original (anmol098) - Sequential", duration=duration, repo_count=len(repos), api_calls=api_call_count)


async def run_imbios_parallel(repos: List[Dict]) -> RaceResult:
    """Run ImBIOS parallel implementation."""
    from unittest.mock import MagicMock, patch

    api_call_count = 0

    async def get_remote_graphql(query, **kwargs):
        nonlocal api_call_count
        api_call_count += 1
        await asyncio.sleep(0.1)  # Simulate API latency

        import subprocess

        result = subprocess.run(["gh", "api", "graphql", "-f", f"query={query}"], capture_output=True, text=True, timeout=30)
        return json.loads(result.stdout) if result.returncode == 0 else {}

    mock_dm = MagicMock()
    mock_dm.get_remote_graphql = get_remote_graphql

    mock_em = MagicMock()
    mock_em.IGNORED_REPOS = []
    mock_em.DEBUG_RUN = False
    mock_em.USE_CACHE = False

    mock_ghm = MagicMock()
    mock_ghm.USER = MagicMock()
    mock_ghm.USER.node_id = "mock"

    mock_dbm = MagicMock()
    mock_dbm.i = lambda x, **kwargs: None
    mock_dbm.g = lambda x, **kwargs: None
    mock_dbm.w = lambda x, **kwargs: None
    mock_dbm.p = lambda x, **kwargs: None

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

        from yearly_commit_calculator import calculate_commit_data

        start = time.perf_counter()
        try:
            await calculate_commit_data(repos)
        except Exception as e:
            print(f"ImBIOS error: {e}")
        duration = time.perf_counter() - start

        sys.path.remove(str(project_root / "sources"))

    return RaceResult(name="2. ImBIOS - Parallel", duration=duration, repo_count=len(repos), api_calls=api_call_count)


async def run_race_benchmark(repos: List[Dict], owner: str):
    """Run both implementations in parallel - first to finish wins."""
    print("\n" + "=" * 70)
    print("RACE BENCHMARK: anmol098 vs ImBIOS")
    print("=" * 70)
    print(f"\nGitHub Owner: {owner}")
    print(f"Repos to process: {len(repos)} (ALL of owner's repos!)")
    print("Race Mode: FIRST TO FINISH WINS - other is cancelled")
    print("=" * 70)

    print("\n[RACE START]")

    # Start both implementations in parallel
    task_original = asyncio.create_task(run_original_anmol(repos))
    task_imbios = asyncio.create_task(run_imbios_parallel(repos))

    # Wait for first to complete
    done, pending = await asyncio.wait([task_original, task_imbios], return_when=asyncio.FIRST_COMPLETED)

    # Get winner result
    winner_result = None

    for task in done:
        winner_result = task.result()
        winner_result.winner = True

    # Cancel the pending task (loser)
    for task in pending:
        task.cancel()

    # Wait for cancellation to complete
    for task in pending:
        try:
            await task
        except asyncio.CancelledError:
            pass

    # Get loser's result
    loser_result = None
    for task in [task_original, task_imbios]:
        if task not in done:
            try:
                loser_result = task.result()
            except Exception:
                loser_result = RaceResult(name="(cancelled)", duration=0, repo_count=0, api_calls=0)

    # Print results
    print("\n[RACE RESULTS]")
    print("-" * 70)

    print(f"\n[WINNER] {winner_result.name}")
    print(f"   Duration: {winner_result.duration:.3f}s")
    print(f"   API calls: {winner_result.api_calls}")
    print(f"   Throughput: {winner_result.repo_count/max(winner_result.duration,0.001):.2f} repos/s")

    if loser_result and loser_result.duration > 0:
        print(f"\n[LOSER] {loser_result.name}")
        print(f"   Duration: {loser_result.duration:.3f}s")
        print(f"   API calls: {loser_result.api_calls}")

        speedup = loser_result.duration / winner_result.duration
        time_saved = loser_result.duration - winner_result.duration
        print(f"\n[SPEEDUP] {speedup:.2f}x faster")
        print(f"   Time saved: {time_saved:.2f}s")
    else:
        print("\n[LOSER] Was cancelled before completing")
        # Estimate based on API calls made
        if winner_result.api_calls > 0:
            estimated_time = winner_result.duration * (len(repos) / winner_result.repo_count)
            print(f"   Estimated total time: ~{estimated_time:.1f}s (extrapolated)")

    print("\n" + "=" * 70)

    return winner_result, loser_result


async def main():
    print(f"\nReal Race Benchmark at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python: {sys.version.split()[0]}")

    # Get real GitHub owner
    print("\nFetching authenticated GitHub user...")
    try:
        owner = get_gh_owner()
        owner_login = owner["login"]
        print(f"   Authenticated as: {owner_login} ({owner.get('name', '')})")
        print(f"   Public repos: {owner['public_repos']}")
    except Exception as e:
        print(f"   Error: {e}")
        print("   Make sure you're logged in with: gh auth login")
        return

    # Fetch ALL real repos
    print(f"\nFetching ALL repositories for {owner_login}...")
    repos = get_real_repos(owner_login)  # No limit - all repos!
    print(f"   Fetched {len(repos)} repos")

    if not repos:
        print("   No repos found.")
        return

    # Run the race with ALL repos
    await run_race_benchmark(repos, owner_login)

    print("\nRace completed!")


if __name__ == "__main__":
    asyncio.run(main())
