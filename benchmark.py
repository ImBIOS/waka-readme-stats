#!/usr/bin/env python3
"""
Benchmarking script for waka-readme-stats

This script runs performance benchmarks on various parts of the codebase
to identify bottlenecks and measure improvements.

Usage:
    python benchmark.py --username <github_username> [--full]

Options:
    --username     GitHub username to use for benchmarking
    --full         Run full benchmark suite (including API calls)
    --no-cache     Disable caching for benchmarking
"""

import argparse
import os
import sys
import time
from pathlib import Path

# Add the parent directory to the path so we can import from sources
parent_dir = Path(__file__).resolve().parent
sys.path.append(str(parent_dir))

from sources.benchmarking import BenchmarkTracker, benchmark
from sources.manager_cache import CacheManager

# Import conditionally to avoid errors if running without full dependencies
try:
    from sources.main import main as waka_main
except ImportError:
    print("Failed to import main module. Make sure all dependencies are installed.")
    sys.exit(1)


@benchmark(name="Full Execution", metadata={"type": "full_run"})
def run_full_benchmark(username, use_cache=True):
    """Run a full benchmark of the waka-readme-stats process.

    Args:
        username: GitHub username to use for benchmarking
        use_cache: Whether to use caching during benchmarking
    """
    # Set up environment variables for the test
    os.environ["INPUT_GH_TOKEN"] = os.environ.get("GH_TOKEN", "")
    os.environ["INPUT_WAKATIME_API_KEY"] = os.environ.get("WAKATIME_API_KEY", "")
    os.environ["INPUT_SHOW_TIMEZONE"] = "True"
    os.environ["INPUT_SHOW_LANGUAGE"] = "True"
    os.environ["INPUT_SHOW_EDITORS"] = "True"
    os.environ["INPUT_SHOW_PROJECTS"] = "True"
    os.environ["INPUT_SHOW_OS"] = "True"
    os.environ["INPUT_SHOW_COMMIT"] = "True"
    os.environ["INPUT_SHOW_LANGUAGE_PER_REPO"] = "True"
    os.environ["GITHUB_REPOSITORY"] = f"{username}/{username}"
    
    # Control caching behavior
    if not use_cache:
        # Clear cache before running
        cache_manager = CacheManager(username)
        cache_manager.clear_cache()
    
    # Run the main function
    try:
        waka_main()
    except Exception as e:
        print(f"Error running benchmark: {e}")


def print_system_info():
    """Print system information for context."""
    import platform
    import multiprocessing
    
    print("System Information:")
    print(f"  - Python version: {platform.python_version()}")
    print(f"  - OS: {platform.system()} {platform.release()}")
    print(f"  - CPU cores: {multiprocessing.cpu_count()}")
    print()


def main():
    """Main benchmark function."""
    parser = argparse.ArgumentParser(description="Benchmark waka-readme-stats")
    parser.add_argument(
        "--username", 
        required=True,
        help="GitHub username to use for benchmarking"
    )
    parser.add_argument(
        "--full", 
        action="store_true", 
        help="Run full benchmark suite (including API calls)"
    )
    parser.add_argument(
        "--no-cache", 
        action="store_true", 
        help="Disable caching for benchmarking"
    )
    
    args = parser.parse_args()
    
    print("Starting benchmarks for waka-readme-stats...\n")
    print_system_info()
    
    # Run with cache
    if not args.no_cache:
        print("Running benchmark with caching enabled...")
        start_time = time.time()
        run_full_benchmark(args.username, use_cache=True)
        print(f"Completed in {time.time() - start_time:.2f}s with caching enabled\n")
    
    # Run without cache for comparison if requested
    if args.no_cache:
        print("Running benchmark with caching disabled...")
        start_time = time.time()
        run_full_benchmark(args.username, use_cache=False)
        print(f"Completed in {time.time() - start_time:.2f}s with caching disabled\n")
    
    # Print detailed benchmark results
    print(BenchmarkTracker.get_summary())


if __name__ == "__main__":
    main()
