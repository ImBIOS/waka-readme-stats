import json
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional


class CacheManager:
    """Manages caching for GitHub repository data to improve performance.

    This class provides functionality to cache and retrieve repository data,
    significantly reducing API calls and processing time for users with many repos.
    """

    CACHE_DIR = ".cache"
    CACHE_EXPIRY = 86400  # Cache expiry in seconds (24 hours)

    def __init__(self, user_id: str):
        """Initialize the cache manager.

        Args:
            user_id: GitHub username or organization name to create user-specific cache
        """
        self.user_id = user_id
        self.cache_path = Path(self.CACHE_DIR) / f"{user_id}_repo_cache.json"
        self._ensure_cache_dir()

    def _ensure_cache_dir(self) -> None:
        """Ensure cache directory exists."""
        os.makedirs(self.CACHE_DIR, exist_ok=True)

    def get_cached_data(self, repo_name: str) -> Optional[Dict[str, Any]]:
        """Get cached data for a specific repository if it exists and is valid.

        Args:
            repo_name: The name of the repository

        Returns:
            The cached repository data or None if not cached or expired
        """
        if not self.cache_path.exists():
            return None

        try:
            with open(self.cache_path, "r") as f:
                cache_data = json.load(f)

            if repo_name not in cache_data:
                return None

            repo_cache = cache_data[repo_name]
            # Check if cache is expired
            if time.time() - repo_cache.get("timestamp", 0) > self.CACHE_EXPIRY:
                return None

            return repo_cache.get("data")
        except (json.JSONDecodeError, IOError):
            # If cache file is corrupted or cannot be read, return None
            return None

    def update_cache(self, repo_name: str, data: Dict[str, Any]) -> None:
        """Update the cache with new repository data.

        Args:
            repo_name: The name of the repository
            data: The repository data to cache
        """
        cache_data = {}
        if self.cache_path.exists():
            try:
                with open(self.cache_path, "r") as f:
                    cache_data = json.load(f)
            except (json.JSONDecodeError, IOError):
                # If cache file is corrupted, start with an empty cache
                cache_data = {}

        # Update cache with new data
        cache_data[repo_name] = {"timestamp": time.time(), "data": data}

        with open(self.cache_path, "w") as f:
            json.dump(cache_data, f)

    def clear_cache(self) -> None:
        """Clear the entire cache for the user."""
        if self.cache_path.exists():
            os.remove(self.cache_path)

    def get_repo_last_modified(self, repo_name: str) -> Optional[float]:
        """Get the last modified timestamp of a cached repository.

        Args:
            repo_name: The name of the repository

        Returns:
            Timestamp of last modification or None if not cached
        """
        if not self.cache_path.exists():
            return None

        try:
            with open(self.cache_path, "r") as f:
                cache_data = json.load(f)

            if repo_name not in cache_data:
                return None

            return cache_data[repo_name].get("timestamp")
        except (json.JSONDecodeError, IOError):
            return None
