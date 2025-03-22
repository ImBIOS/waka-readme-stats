import os
import time
from pathlib import Path

import pytest

from manager_cache import CacheManager


@pytest.fixture
def cache_manager():
    manager = CacheManager("test_user")
    # Ensure clean state for tests
    if Path(CacheManager.CACHE_DIR, "test_user_repo_cache.json").exists():
        os.remove(Path(CacheManager.CACHE_DIR, "test_user_repo_cache.json"))
    yield manager
    # Clean up after tests
    if Path(CacheManager.CACHE_DIR, "test_user_repo_cache.json").exists():
        os.remove(Path(CacheManager.CACHE_DIR, "test_user_repo_cache.json"))


def test_ensure_cache_dir_creation(cache_manager):
    """Test that the cache directory is created."""
    assert Path(CacheManager.CACHE_DIR).exists()


def test_get_cached_data_no_cache_file(cache_manager):
    """Test getting data when no cache file exists."""
    assert cache_manager.get_cached_data("repo1") is None


def test_update_and_get_cache(cache_manager):
    """Test updating and retrieving cache."""
    test_data = {"name": "repo1", "language": "Python"}
    cache_manager.update_cache("repo1", test_data)

    assert Path(CacheManager.CACHE_DIR, "test_user_repo_cache.json").exists()
    assert cache_manager.get_cached_data("repo1") == test_data


def test_update_existing_cache(cache_manager):
    """Test updating existing cache entry."""
    # Set initial data
    initial_data = {"name": "repo1", "language": "Python"}
    cache_manager.update_cache("repo1", initial_data)

    # Update with new data
    updated_data = {"name": "repo1", "language": "JavaScript"}
    cache_manager.update_cache("repo1", updated_data)

    # Verify update worked
    assert cache_manager.get_cached_data("repo1") == updated_data


def test_multiple_repos_cache(cache_manager):
    """Test caching multiple repositories."""
    repo1_data = {"name": "repo1", "language": "Python"}
    repo2_data = {"name": "repo2", "language": "JavaScript"}

    cache_manager.update_cache("repo1", repo1_data)
    cache_manager.update_cache("repo2", repo2_data)

    assert cache_manager.get_cached_data("repo1") == repo1_data
    assert cache_manager.get_cached_data("repo2") == repo2_data


def test_clear_cache(cache_manager):
    """Test clearing the cache."""
    # Add some data
    cache_manager.update_cache("repo1", {"data": "test"})

    # Verify it exists
    assert cache_manager.get_cached_data("repo1") is not None

    # Clear and verify it's gone
    cache_manager.clear_cache()
    assert cache_manager.get_cached_data("repo1") is None
    assert not Path(CacheManager.CACHE_DIR, "test_user_repo_cache.json").exists()


def test_cache_expiry(cache_manager, monkeypatch):
    """Test that expired cache entries are not returned."""
    # Add data
    cache_manager.update_cache("repo1", {"data": "test"})

    # Verify it exists
    assert cache_manager.get_cached_data("repo1") is not None

    # Mock time to simulate passage of time beyond expiry
    current_time = time.time()
    future_time = current_time + CacheManager.CACHE_EXPIRY + 100
    monkeypatch.setattr(time, "time", lambda: future_time)

    # Verify expired cache is not returned
    assert cache_manager.get_cached_data("repo1") is None


def test_corrupted_cache_file(cache_manager):
    """Test handling of corrupted cache files."""
    # Create a corrupted JSON file
    os.makedirs(CacheManager.CACHE_DIR, exist_ok=True)
    with open(Path(CacheManager.CACHE_DIR, "test_user_repo_cache.json"), "w") as f:
        f.write('{"not valid JSON"')

    # Should handle gracefully and return None
    assert cache_manager.get_cached_data("repo1") is None

    # Should be able to update cache even after corruption
    cache_manager.update_cache("repo1", {"data": "new"})
    assert cache_manager.get_cached_data("repo1") == {"data": "new"}


def test_get_repo_last_modified(cache_manager, monkeypatch):
    """Test getting the last modified timestamp."""
    # Mock time for consistent testing
    test_time = 1617000000.0
    monkeypatch.setattr(time, "time", lambda: test_time)

    # Add data
    cache_manager.update_cache("repo1", {"data": "test"})

    # Check timestamp
    assert cache_manager.get_repo_last_modified("repo1") == test_time

    # Non-existent repo
    assert cache_manager.get_repo_last_modified("non_existent") is None


def test_get_repo_last_modified_no_cache(cache_manager):
    """Test getting timestamp when no cache exists."""
    assert cache_manager.get_repo_last_modified("repo1") is None
