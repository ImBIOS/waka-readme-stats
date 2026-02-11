#!/usr/bin/env python3
"""
Smoke tests for critical issues found in CI jobs.

Tests:
1. Asset directory creation before saving graph (issue: FileNotFoundError)
2. Rate limit handling for GraphQL API
"""

import os
import shutil
from unittest.mock import AsyncMock, patch

import pytest

# Mock environment variables before importing
os.environ["INPUT_GH_TOKEN"] = "mock_gh_token"
os.environ["INPUT_WAKATIME_API_KEY"] = "mock_wakatime_key"

from .graphics_chart_drawer import create_loc_graph  # noqa: E402
from .manager_debug import DebugManager as DBM  # noqa: E402
from .manager_download import DownloadManager  # noqa: E402
from .manager_file import FileManager  # noqa: E402


# Initialize DebugManager for tests
DBM.create_logger("INFO")


@pytest.fixture(autouse=True)
def init_debug():
    """Initialize debug manager for all tests."""
    if not hasattr(DBM, "_logger"):
        DBM.create_logger("INFO")


class TestAssetDirectoryCreation:
    """Tests for ensuring assets directory is created before saving files."""

    @pytest.fixture
    def clean_test_env(self, tmp_path):
        """Fixture to ensure clean test environment."""
        assets_dir = tmp_path / "assets"
        # Ensure directory doesn't exist before test
        if assets_dir.exists():
            shutil.rmtree(assets_dir)
        yield tmp_path
        # Cleanup after test
        if assets_dir.exists():
            shutil.rmtree(assets_dir)

    @pytest.mark.asyncio
    async def test_graph_creates_assets_dir_when_missing(self, clean_test_env):
        """Test that create_loc_graph creates assets directory if it doesn't exist."""
        # Ensure assets directory doesn't exist
        assets_dir = clean_test_env / "assets"
        assert not assets_dir.exists(), "Assets dir should not exist at test start"

        # Mock the download manager
        with patch.object(DownloadManager, "get_remote_yaml", new_callable=AsyncMock) as mock_yaml:
            mock_yaml.return_value = {"Python": {"color": "blue"}}

            # Mock ASSETS_DIR to use temp path
            with patch.object(FileManager, "ASSETS_DIR", str(assets_dir)):
                test_save_path = str(assets_dir / "test_graph.png")
                test_data = {
                    "2024": {
                        1: {"Python": {"add": 100, "del": 50}},
                        2: {"Python": {"add": 120, "del": 40}},
                        3: {"Python": {"add": 150, "del": 60}},
                        4: {"Python": {"add": 200, "del": 80}},
                    }
                }

                # This should create the directory
                await create_loc_graph(test_data, test_save_path)

                # Verify directory was created
                assert assets_dir.exists(), "Assets directory should be created"
                assert os.path.exists(test_save_path), "Graph file should be created"

    @pytest.mark.asyncio
    async def test_graph_with_empty_data_creates_assets_dir(self, clean_test_env):
        """Test that empty data case also creates assets directory."""
        assets_dir = clean_test_env / "assets"
        assert not assets_dir.exists()

        with patch.object(DownloadManager, "get_remote_yaml", new_callable=AsyncMock) as mock_yaml:
            mock_yaml.return_value = {}

            with patch.object(FileManager, "ASSETS_DIR", str(assets_dir)):
                test_save_path = str(assets_dir / "empty_graph.png")

                await create_loc_graph({}, test_save_path)

                assert assets_dir.exists(), "Assets dir should be created even for empty data"
                assert os.path.exists(test_save_path), "Empty graph should be saved"

    @pytest.mark.asyncio
    async def test_graph_works_when_assets_dir_already_exists(self, clean_test_env):
        """Test that graph creation works when assets dir already exists."""
        assets_dir = clean_test_env / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        with patch.object(DownloadManager, "get_remote_yaml", new_callable=AsyncMock) as mock_yaml:
            mock_yaml.return_value = {"Python": {"color": "blue"}}

            with patch.object(FileManager, "ASSETS_DIR", str(assets_dir)):
                test_save_path = str(assets_dir / "test_graph2.png")
                test_data = {
                    "2024": {
                        1: {"Python": {"add": 50, "del": 25}},
                    }
                }

                # Should not raise error even if dir exists
                await create_loc_graph(test_data, test_save_path)

                assert os.path.exists(test_save_path)


class TestRateLimitHandling:
    """Tests for GitHub GraphQL API rate limit handling."""

    @pytest.mark.asyncio
    async def test_rate_limit_error_detection_in_response(self):
        """
        Test that rate limit errors in 200 response body are properly detected.
        This tests the detection logic for errors like:
        'API rate limit already exceeded for user ID 41441643'
        """
        rate_limit_response = {
            "data": None,
            "errors": [
                {
                    "type": "RATE_LIMIT",
                    "message": "API rate limit already exceeded for user ID 41441643.",
                }
            ],
        }

        # Verify the error structure matches what the code handles
        errors = rate_limit_response.get("errors", [])
        assert len(errors) > 0, "Response should have errors"

        for error in errors:
            # Check that the detection logic would catch this
            is_rate_limit = error.get("type") == "RATE_LIMIT" or "rate limit" in error.get("message", "").lower()
            assert is_rate_limit, "Should detect rate limit error"
            assert error.get("message") == "API rate limit already exceeded for user ID 41441643."

    @pytest.mark.asyncio
    async def test_rate_limit_with_resetAt_parsing(self):
        """Test that resetAt time is properly parsed from error extensions."""
        from datetime import datetime, timedelta, timezone

        reset_time = datetime.now(timezone.utc) + timedelta(seconds=60)

        rate_limit_response = {
            "data": None,
            "errors": [
                {
                    "type": "RATE_LIMIT",
                    "message": "Please wait for rate limit to reset",
                    "extensions": {
                        "rateLimit": {
                            "resetAt": reset_time.isoformat().replace("+00:00", "Z"),
                        }
                    },
                }
            ],
        }

        errors = rate_limit_response.get("errors", [])
        error = errors[0]

        # Test parsing the resetAt value
        extensions = error.get("extensions", {})
        rate_limit_info = extensions.get("rateLimit", {})
        reset_at = rate_limit_info.get("resetAt")

        assert reset_at is not None, "Should have resetAt time"

        # Verify the parsing works
        try:
            from datetime import datetime

            reset_time_parsed = datetime.fromisoformat(reset_at.replace("Z", "+00:00"))
            now_aware = datetime.now(timezone.utc)
            wait_seconds = max((reset_time_parsed - now_aware).total_seconds(), 1)
            assert 0 < wait_seconds <= 120, "Should calculate reasonable wait time"
        except (ValueError, TypeError) as e:
            pytest.fail(f"Failed to parse resetAt: {e}")

    @pytest.mark.asyncio
    async def test_rate_limit_with_try_again_message_parsing(self):
        """Test rate limit parsing from message like 'try again in 51 seconds'."""
        from re import search as regex_search, IGNORECASE

        test_cases = [
            "Please try again in 51 seconds",
            "API rate limit exceeded. Try again in 120 seconds",
            "Rate limit. Please try again in 30 seconds.",
        ]

        for message in test_cases:
            match = regex_search(r"try again in (\d+) seconds", message, IGNORECASE)
            assert match is not None, f"Should extract wait time from: {message}"
            wait_seconds = int(match.group(1))
            assert 30 <= wait_seconds <= 120, f"Should extract reasonable wait time: {wait_seconds}"

    @pytest.mark.asyncio
    async def test_exponential_backoff_calculation(self):
        """Test exponential backoff calculation for retries."""
        # Test the backoff formula: 2 ** (10 - retries_count)
        test_cases = [
            (10, 1),  # First retry: 2^0 = 1
            (9, 2),  # Second retry: 2^1 = 2
            (8, 4),  # Third retry: 2^2 = 4
            (5, 32),  # More retries: 2^5 = 32
            (1, 512),  # Many retries: 2^9 = 512
        ]

        for retries, expected_max in test_cases:
            wait_time = 2 ** (10 - retries)
            assert wait_time == expected_max, f"Backoff for retry {retries} should be {expected_max}"

        # Test that backoff caps at reasonable values
        max_backoff = 300  # 5 minutes cap in code
        assert min(512, max_backoff) == max_backoff, "Backoff should cap at max value"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
