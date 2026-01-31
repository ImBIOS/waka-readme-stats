#!/usr/bin/env python3
"""
Simulate what the Waka Trigger workflow would do locally.
This tests the action execution without GitHub Actions.
"""

import os
import sys
from pathlib import Path

# Setup
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "sources"))

# Set required environment variables
os.environ["INPUT_GH_TOKEN"] = os.environ.get("GH_TOKEN", "")
os.environ["INPUT_WAKATIME_API_KEY"] = os.environ.get("WAKATIME_API_KEY", "test_key")
os.environ["INPUT_SECTION_NAME"] = "CodingStats"
os.environ["INPUT_SHOW_PROJECTS"] = "False"
os.environ["INPUT_COMMIT_MESSAGE"] = "Updated waka-readme graph with new metrics"
os.environ["INPUT_USE_CACHE"] = "True"
os.environ["INPUT_CACHE_TTL_DAYS"] = "7"
os.environ["INPUT_MAX_CONCURRENCY"] = "16"

print("=" * 70)
print("SIMULATING: Waka Trigger Workflow")
print("=" * 70)
print("\nConfiguration:")
print(f"  GH_TOKEN: {'Set' if os.environ.get('INPUT_GH_TOKEN') else 'NOT SET'}")
print(f"  WAKATIME_API_KEY: {'Set' if os.environ.get('INPUT_WAKATIME_API_KEY') else 'NOT SET'}")
print(f"  SECTION_NAME: {os.environ.get('INPUT_SECTION_NAME')}")
print(f"  SHOW_PROJECTS: {os.environ.get('INPUT_SHOW_PROJECTS')}")
print(f"  COMMIT_MESSAGE: {os.environ.get('INPUT_COMMIT_MESSAGE')}")
print(f"  USE_CACHE: {os.environ.get('INPUT_USE_CACHE')}")
print("=" * 70)

# Check if we can import the main module
try:
    from manager_environment import EnvironmentManager

    em = EnvironmentManager()
    print("\n[OK] Environment Manager loaded")
    print(f"  GH_TOKEN: {'***' if em.GH_TOKEN else 'NOT SET'}")
    print(f"  USE_CACHE: {em.USE_CACHE}")

    # Check GitHub connection
    import subprocess

    result = subprocess.run(["gh", "api", "user"], capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        import json

        user = json.loads(result.stdout)
        print(f"\n[OK] GitHub CLI authenticated as: {user['login']}")
        print(f"  Name: {user.get('name', 'N/A')}")
        print(f"  Public repos: {user['public_repos']}")
    else:
        print("\n[WARN] GitHub CLI not authenticated")

    print("\n" + "=" * 70)
    print("WORKFLOW SIMULATION COMPLETE")
    print("=" * 70)
    print(
        """
The workflow would:
1. Fetch WakaTime stats using INPUT_WAKATIME_API_KEY
2. Fetch GitHub commit data using INPUT_GH_TOKEN
3. Update the README with new metrics in SECTION_NAME
4. Commit changes with INPUT_COMMIT_MESSAGE

If the job fails, the 'rerun-failed-jobs' step would:
- Re-run the failed job using 'gh run rerun'
"""
    )

except Exception as e:
    print(f"\n[ERROR] {e}")
    import traceback

    traceback.print_exc()
