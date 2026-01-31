import os
import sys
import types
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

import pytest

# Stub heavy deps used transitively by modules to avoid installing them for this unit
if "humanize" not in sys.modules:
    humanize_stub = types.ModuleType("humanize")

    def _precisedelta_stub(*args, **kwargs):
        return "0s"

    humanize_stub.precisedelta = _precisedelta_stub
    sys.modules["humanize"] = humanize_stub

if "matplotlib" not in sys.modules:
    matplotlib_stub = types.ModuleType("matplotlib")
    patches_stub = types.ModuleType("matplotlib.patches")
    sys.modules["matplotlib"] = matplotlib_stub
    sys.modules["matplotlib.patches"] = patches_stub

if "github" not in sys.modules:
    github_stub = types.ModuleType("github")

    class _Dummy:  # minimal placeholders
        pass

    github_stub.Github = _Dummy
    github_stub.AuthenticatedUser = _Dummy
    github_stub.Repository = _Dummy
    sys.modules["github"] = github_stub

# Mock environment variables before importing the modules
os.environ["INPUT_GH_TOKEN"] = "mock_gh_token"
os.environ["INPUT_WAKATIME_API_KEY"] = "mock_wakatime_key"

from .yearly_commit_calculator import calculate_commit_data, update_data_with_commit_stats  # noqa: E402
from .manager_debug import DebugManager as DBM  # noqa: E402


@pytest.fixture(autouse=True)
def mock_environment():
    """Fixture to ensure environment variables are set for all tests"""
    with patch.dict(
        os.environ,
        {
            "INPUT_GH_TOKEN": "mock_gh_token",
            "INPUT_WAKATIME_API_KEY": "mock_wakatime_key",
            "DEBUG_RUN": "False",
            "INPUT_IGNORED_REPOS": "",
        },
    ):
        yield


@pytest.fixture(autouse=True)
def init_logger():
    DBM.create_logger("ERROR")


@pytest.mark.asyncio
async def test_calculate_commit_data_debug_run_with_cache():
    """Test calculate_commit_data in debug mode with cached data"""
    repositories = [{"name": "test-repo"}]

    mock_cache = (
        {"2023": {1: {"Python": {"add": 100, "del": 50}}}},
        {"test-repo": {"main": {"commit1": "2023-01-15T10:00:00Z"}}},
    )

    with patch("sources.yearly_commit_calculator.EM") as mock_em:
        mock_em.DEBUG_RUN = True
        mock_em.IGNORED_REPOS = []

        with patch("sources.yearly_commit_calculator.FM") as mock_fm:
            mock_fm.cache_binary.return_value = mock_cache
            mock_fm.t.return_value = "test"

            yearly_data, commit_data = await calculate_commit_data(repositories)

            assert yearly_data == mock_cache[0]
            assert commit_data == mock_cache[1]
            mock_fm.cache_binary.assert_called_once()


@pytest.mark.asyncio
async def test_calculate_commit_data_debug_run_no_cache():
    """Test calculate_commit_data in debug mode without cached data"""
    repositories = [
        {
            "name": "test-repo",
            "isPrivate": False,
            "owner": {"login": "testuser"},
            "primaryLanguage": {"name": "Python"},
        }
    ]

    mock_branch_data = [{"name": "main"}]
    mock_commit_data = [
        {
            "oid": "abc123",
            "committedDate": "2023-01-15T10:00:00Z",
            "additions": 100,
            "deletions": 50,
        }
    ]

    with patch("sources.yearly_commit_calculator.EM") as mock_em:
        mock_em.DEBUG_RUN = True
        mock_em.IGNORED_REPOS = []

        with patch("sources.yearly_commit_calculator.DM") as mock_dm:
            mock_dm.get_remote_graphql = AsyncMock(side_effect=[mock_branch_data, mock_commit_data])

            with patch("sources.yearly_commit_calculator.GHM") as mock_ghm:
                mock_ghm.USER.node_id = "user123"

                with patch("sources.yearly_commit_calculator.FM") as mock_fm:
                    mock_fm.cache_binary.side_effect = [None, None]  # No cache
                    mock_fm.write_file = MagicMock()
                    mock_fm.t.return_value = "test"

                    yearly_data, commit_data = await calculate_commit_data(repositories)

                    assert 2023 in yearly_data
                    assert 1 in yearly_data[2023]
                    assert "Python" in yearly_data[2023][1]
                    assert yearly_data[2023][1]["Python"]["add"] == 100
                    assert yearly_data[2023][1]["Python"]["del"] == 50

                    assert "test-repo" in commit_data
                    assert "main" in commit_data["test-repo"]


@pytest.mark.asyncio
async def test_calculate_commit_data_ignored_repos():
    """Test calculate_commit_data with ignored repositories"""
    repositories = [
        {"name": "ignored-repo", "isPrivate": False, "owner": {"login": "testuser"}, "primaryLanguage": {"name": "Python"}},
        {"name": "valid-repo", "isPrivate": False, "owner": {"login": "testuser"}, "primaryLanguage": {"name": "Python"}},
    ]

    with patch("sources.yearly_commit_calculator.EM") as mock_em:
        mock_em.DEBUG_RUN = False
        mock_em.IGNORED_REPOS = ["ignored-repo"]

        with patch("sources.yearly_commit_calculator.DM") as mock_dm:
            mock_dm.get_remote_graphql = AsyncMock(side_effect=[[], []])  # Empty branch data

            with patch("sources.yearly_commit_calculator.FM") as mock_fm:
                mock_fm.t.return_value = "test"

                yearly_data, commit_data = await calculate_commit_data(repositories)

                # Should only process valid-repo
                assert isinstance(yearly_data, dict)
                assert isinstance(commit_data, dict)


@pytest.mark.asyncio
async def test_update_data_with_commit_stats():
    """Test update_data_with_commit_stats function"""
    repo_details = {
        "name": "test-repo",
        "owner": {"login": "testuser"},
        "primaryLanguage": {"name": "Python"},
    }
    yearly_data = {}
    date_data = {}

    mock_branch_data = [{"name": "main"}]
    mock_commit_data = [
        {
            "oid": "commit1",
            "committedDate": "2023-04-15T10:00:00Z",  # Q2 2023
            "additions": 150,
            "deletions": 60,
        }
    ]

    with patch("sources.yearly_commit_calculator.DM") as mock_dm:
        mock_dm.get_remote_graphql = AsyncMock(side_effect=[mock_branch_data, mock_commit_data])

        with patch("sources.yearly_commit_calculator.GHM") as mock_ghm:
            mock_ghm.USER.node_id = "user123"

            with patch("sources.yearly_commit_calculator.FM") as mock_fm:
                mock_fm.t.return_value = "test"

                await update_data_with_commit_stats(repo_details, yearly_data, date_data)

                assert 2023 in yearly_data
                assert 2 in yearly_data[2023]  # Q2
                assert "Python" in yearly_data[2023][2]
                assert yearly_data[2023][2]["Python"]["add"] == 150
                assert yearly_data[2023][2]["Python"]["del"] == 60

                assert "test-repo" in date_data
                assert "main" in date_data["test-repo"]
                assert "commit1" in date_data["test-repo"]["main"]


@pytest.mark.asyncio
async def test_update_data_with_commit_stats_no_branches():
    """Test update_data_with_commit_stats when no branches are found"""
    repo_details = {"name": "test-repo", "owner": {"login": "testuser"}, "primaryLanguage": {"name": "Python"}}
    yearly_data = {}
    date_data = {}

    with patch("sources.yearly_commit_calculator.DM") as mock_dm:
        mock_dm.get_remote_graphql = AsyncMock(return_value=[])  # No branches

        with patch("sources.yearly_commit_calculator.FM") as mock_fm:
            mock_fm.t.return_value = "test"

            await update_data_with_commit_stats(repo_details, yearly_data, date_data)

            assert yearly_data == {}
            assert date_data == {}


@pytest.mark.asyncio
async def test_update_data_with_commit_stats_no_primary_language():
    """Test update_data_with_commit_stats with no primary language"""
    repo_details = {
        "name": "test-repo",
        "owner": {"login": "testuser"},
        "primaryLanguage": None,
    }
    yearly_data = {}
    date_data = {}

    mock_branch_data = [{"name": "main"}]
    mock_commit_data = [
        {
            "oid": "commit1",
            "committedDate": "2023-01-15T10:00:00Z",
            "additions": 100,
            "deletions": 50,
        }
    ]

    with patch("sources.yearly_commit_calculator.DM") as mock_dm:
        mock_dm.get_remote_graphql = AsyncMock(side_effect=[mock_branch_data, mock_commit_data])

        with patch("sources.yearly_commit_calculator.GHM") as mock_ghm:
            mock_ghm.USER.node_id = "user123"

            with patch("sources.yearly_commit_calculator.FM") as mock_fm:
                mock_fm.t.return_value = "test"

                await update_data_with_commit_stats(repo_details, yearly_data, date_data)

                # Should still update date_data but not yearly_data
                assert "test-repo" in date_data
                assert 2023 not in yearly_data or 1 not in yearly_data[2023]


@pytest.mark.asyncio
async def test_calculate_commit_data_runs_in_parallel(monkeypatch):
    """Ensure multiple repositories are processed concurrently (bounded).

    We simulate IO by sleeping inside mocked graphql calls. With 4 repos and
    two awaited calls per repo (branches then commits), sequential time would be
    roughly 4 * 2 * unit_sleep. With concurrency this should be much lower.
    """
    unit_sleep = 0.05

    repositories = [{"name": f"repo-{i}", "isPrivate": False, "owner": {"login": "u"}, "primaryLanguage": {"name": "Python"}} for i in range(4)]

    from asyncio import sleep as asyncio_sleep

    async def mock_get_remote_graphql(query_name, **kwargs):
        if query_name == "repo_branch_list":
            await asyncio_sleep(unit_sleep)
            return [{"name": "main"}]
        if query_name == "repo_commit_list":
            await asyncio_sleep(unit_sleep)
            return [
                {
                    "oid": "c1",
                    "committedDate": "2023-01-15T10:00:00Z",
                    "additions": 1,
                    "deletions": 1,
                }
            ]
        return []

    # Force high concurrency so it's not the bottleneck
    monkeypatch.setenv("INPUT_MAX_CONCURRENCY", "16")

    with patch("sources.yearly_commit_calculator.EM") as mock_em:
        mock_em.DEBUG_RUN = True
        mock_em.IGNORED_REPOS = []

        with patch("sources.yearly_commit_calculator.DM") as mock_dm:
            mock_dm.get_remote_graphql = AsyncMock(side_effect=mock_get_remote_graphql)
            with patch("sources.yearly_commit_calculator.GHM") as mock_ghm:
                mock_ghm.USER.node_id = "user123"

                start = datetime.now()
                yearly_data, commit_data = await calculate_commit_data(repositories)
                elapsed = (datetime.now() - start).total_seconds()

                # Sanity: data produced
                assert isinstance(yearly_data, dict)
                assert isinstance(commit_data, dict)

                # Sequential lower bound ~ 4 repos * 2 sleeps = 8 * unit_sleep
                sequential_est = 8 * unit_sleep
                # Parallel should be significantly faster than sequential; allow slack
                assert elapsed < sequential_est * 0.6
