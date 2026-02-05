from asyncio import Semaphore, gather, sleep
from datetime import datetime, timedelta
from json import dumps, loads
from os import cpu_count, getenv, makedirs
from os.path import isfile
from re import search
from typing import Dict, Optional, Tuple

from .manager_debug import DebugManager as DBM
from .manager_download import DownloadManager as DM
from .manager_environment import EnvironmentManager as EM
from .manager_file import FileManager as FM
from .manager_github import GitHubManager as GHM

# Cache directory for repo data
CACHE_DIR = ".repo_cache"
CACHE_INDEX_FILE = f"{CACHE_DIR}/index.json"
CHECKPOINT_FILE = f"{CACHE_DIR}/checkpoint.json"


def get_repo_cache_path(repo_name: str) -> str:
    """Get the cache file path for a specific repo."""
    return f"{CACHE_DIR}/{repo_name.replace('/', '_')}.json"


def get_cache_index() -> Dict:
    """Load the cache index containing last update times for each repo."""
    if isfile(CACHE_INDEX_FILE):
        try:
            with open(CACHE_INDEX_FILE, "r") as f:
                return loads(f.read())
        except Exception:
            return {}
    return {}


def save_cache_index(index: Dict) -> None:
    """Save the cache index with last update times."""
    makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_INDEX_FILE, "w") as f:
        f.write(dumps(index, indent=2))


def get_checkpoint() -> Dict:
    """Load checkpoint to track processed repos for resumable runs."""
    if isfile(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, "r") as f:
                return loads(f.read())
        except Exception:
            return {"processed_repos": [], "completed_at": None}
    return {"processed_repos": [], "completed_at": None}


def save_checkpoint(processed_repos: list, completed: bool = False) -> None:
    """Save checkpoint after processing each repo."""
    checkpoint = {
        "processed_repos": processed_repos,
        "completed_at": datetime.now().isoformat() if completed else None,
    }
    makedirs(CACHE_DIR, exist_ok=True)
    with open(CHECKPOINT_FILE, "w") as f:
        f.write(dumps(checkpoint, indent=2))


def clear_checkpoint() -> None:
    """Clear checkpoint when run completes successfully."""
    if isfile(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "w") as f:
            f.write(dumps({"processed_repos": [], "completed_at": None}, indent=2))


def get_cached_repo_data(repo_name: str) -> Optional[Dict]:
    """Load cached data for a specific repo."""
    cache_path = get_repo_cache_path(repo_name)
    if isfile(cache_path):
        try:
            with open(cache_path, "r") as f:
                return loads(f.read())
        except Exception:
            return None
    return None


def save_repo_to_cache(repo_name: str, data: Dict, index: Dict) -> None:
    """Save repo data to cache and update index."""
    cache_path = get_repo_cache_path(repo_name)
    makedirs(CACHE_DIR, exist_ok=True)
    with open(cache_path, "w") as f:
        f.write(dumps(data, indent=2))
    index[repo_name] = datetime.now().isoformat()
    save_cache_index(index)


async def calculate_commit_data(repositories: Dict) -> Tuple[Dict, Dict]:
    """
    Calculate commit data by years with smart caching and checkpoint/resume support.
    Only fetches repos that have been updated since last run.
    Supports resuming from previous partial runs via checkpoint file.

    Commit data includes contribution additions and deletions in each quarter of each recorded year.

    :param repositories: user repositories info dictionary.
    :returns: Commit quarter yearly data dictionary.
    """
    DBM.i("Calculating commit data with smart caching and checkpoint support...")

    # Check if we should use cache
    use_cache = getenv("INPUT_USE_CACHE", "true").lower() == "true"
    cache_ttl_days = int(getenv("INPUT_CACHE_TTL_DAYS", "7"))

    yearly_data = dict()
    date_data = dict()

    if use_cache:
        cache_index = get_cache_index()
        checkpoint = get_checkpoint()
        processed_repos = checkpoint.get("processed_repos", [])
        cutoff_date = datetime.now() - timedelta(days=cache_ttl_days)

        repos_to_fetch = []
        repos_to_load = []

        for repo in repositories:
            repo_name = repo["name"]
            if repo_name in EM.IGNORED_REPOS:
                continue

            # Resume from checkpoint: skip repos already processed in previous run
            if processed_repos and repo_name in processed_repos:
                DBM.i(f"Resuming: {repo_name} was processed in previous run, loading from cache")
                repos_to_load.append(repo)
                continue

            last_cached_str = cache_index.get(repo_name)

            if last_cached_str is None:
                # Never cached, need to fetch
                repos_to_fetch.append(repo)
            else:
                try:
                    last_cached = datetime.fromisoformat(last_cached_str)
                    if last_cached < cutoff_date:
                        # Cache expired, refetch
                        repos_to_fetch.append(repo)
                    else:
                        # Valid cache, load from cache
                        repos_to_load.append(repo)
                except Exception:
                    repos_to_fetch.append(repo)

        DBM.i(f"Cache strategy: {len(repos_to_fetch)} repos to fetch, {len(repos_to_load)} from cache")
        if processed_repos:
            DBM.i(f"Checkpoint resume: skipping {len(processed_repos)} already processed repos")

        # Process repos that need fetching in parallel (with checkpoint support)
        if repos_to_fetch:
            await fetch_and_process_repos(repos_to_fetch, yearly_data, date_data, cache_index, processed_repos)

        # Load cached data for unchanged repos
        for repo in repos_to_load:
            await load_cached_repo_data(repo, yearly_data, date_data)

        # Clear checkpoint on successful completion
        clear_checkpoint()
    else:
        # No caching, fetch all repos
        DBM.i("Cache disabled, fetching all repositories...")
        cache_index = {}
        await fetch_and_process_repos(repositories, yearly_data, date_data, cache_index, [])

    DBM.g("Commit data calculated!")

    if EM.DEBUG_RUN:
        FM.cache_binary("commits_data.pick", [yearly_data, date_data], assets=True)
        FM.write_file("commits_data.json", dumps([yearly_data, date_data]), assets=True)
        DBM.g("Commit data saved to cache!")

    return yearly_data, date_data


async def fetch_and_process_repos(repositories: Dict, yearly_data: Dict, date_data: Dict, cache_index: Dict, processed_repos: list) -> None:
    """Fetch and process repositories in parallel with semaphore control and checkpoint support."""
    # Determine concurrency
    configured = getenv("INPUT_MAX_CONCURRENCY", "")
    try:
        max_concurrency = int(configured) if configured else 0
    except ValueError:
        max_concurrency = 0
    if max_concurrency <= 0:
        cores = cpu_count() or 4
        max_concurrency = max(2, min(cores, 16))

    sem = Semaphore(max_concurrency)

    async def process_one(index: int, repo: Dict) -> None:
        if repo["name"] in EM.IGNORED_REPOS:
            return
        repo_name = "[private]" if repo["isPrivate"] else f"{repo['owner']['login']}/{repo['name']}"
        DBM.i(f"\t{index + 1}/{len(repositories)} Fetching repo: {repo_name}")
        async with sem:
            await update_data_with_commit_stats_and_cache(repo, yearly_data, date_data, cache_index)
        # Save checkpoint after each repo for resumable runs
        if repo["name"] not in processed_repos:
            processed_repos.append(repo["name"])
            save_checkpoint(processed_repos)

    tasks = [process_one(ind, repo) for ind, repo in enumerate(repositories)]
    DBM.i(f"Fetching {len(repositories)} repositories...")
    if tasks:
        await gather(*tasks)


async def load_cached_repo_data(repo: Dict, yearly_data: Dict, date_data: Dict) -> None:
    """Load previously cached data for a repository."""
    repo_name = repo["name"]
    cached = get_cached_repo_data(repo_name)

    if cached is None:
        return

    repo_name_display = "[private]" if repo["isPrivate"] else f"{repo['owner']['login']}/{repo_name}"
    DBM.i(f"\tLoading from cache: {repo_name_display}")

    # Merge cached data into yearly_data and date_data
    for year, quarters in cached.get("yearly_data", {}).items():
        if year not in yearly_data:
            yearly_data[year] = {}
        for quarter, languages in quarters.items():
            if quarter not in yearly_data[year]:
                yearly_data[year][quarter] = {}
            for lang, stats in languages.items():
                if lang not in yearly_data[year][quarter]:
                    yearly_data[year][quarter][lang] = {"add": 0, "del": 0}
                yearly_data[year][quarter][lang]["add"] += stats.get("add", 0)
                yearly_data[year][quarter][lang]["del"] += stats.get("del", 0)

    # Copy date_data
    if repo_name not in date_data:
        date_data[repo_name] = {}
    for branch, commits in cached.get("date_data", {}).items():
        date_data[repo_name][branch] = commits


async def update_data_with_commit_stats_and_cache(repo_details: Dict, yearly_data: Dict, date_data: Dict, cache_index: Dict) -> None:
    """
    Updates yearly commit data with commits from given repository.
    Saves result to cache for future runs.
    Skips update if the commit isn't related to any repository.

    :param repo_details: Dictionary with information about the given repository.
    :param yearly_data: Yearly data dictionary to update.
    :param date_data: Commit date dictionary to update.
    :param cache_index: Cache index to update.
    """
    owner = repo_details["owner"]["login"]
    repo_name = repo_details["name"]

    branch_data = await DM.get_remote_graphql("repo_branch_list", owner=owner, name=repo_name)
    if len(branch_data) == 0:
        DBM.w(f"\t\tBranch data not found, skipping {repo_name} repository...")
        return

    # Local storage for this repo's data
    repo_yearly_data = {}
    repo_date_data = {}

    for branch in branch_data:
        DBM.i(f"\t\tProcessing {repo_name} branch: {branch['name']}")
        commit_data = await DM.get_remote_graphql(
            "repo_commit_list",
            owner=owner,
            name=repo_name,
            branch=branch["name"],
            id=GHM.USER.node_id,
        )
        DBM.i(f"\t\t\tFound {len(commit_data)} commits in {repo_name} branch {branch['name']}")

        # Initialize branch in date_data
        if repo_name not in repo_date_data:
            repo_date_data[repo_name] = {}
        if branch["name"] not in repo_date_data[repo_name]:
            repo_date_data[repo_name][branch["name"]] = {}

        for commit in commit_data:
            date = search(r"\d+-\d+-\d+", commit["committedDate"]).group()
            curr_year = datetime.fromisoformat(date).year
            quarter = (datetime.fromisoformat(date).month - 1) // 3 + 1

            repo_date_data[repo_name][branch["name"]][commit["oid"]] = commit["committedDate"]

            if repo_details["primaryLanguage"] is not None:
                plang = repo_details["primaryLanguage"]["name"]
                if curr_year not in repo_yearly_data:
                    repo_yearly_data[curr_year] = dict()
                if quarter not in repo_yearly_data[curr_year]:
                    repo_yearly_data[curr_year][quarter] = dict()
                if plang not in repo_yearly_data[curr_year][quarter]:
                    repo_yearly_data[curr_year][quarter][plang] = {"add": 0, "del": 0}
                repo_yearly_data[curr_year][quarter][plang]["add"] += commit["additions"]
                repo_yearly_data[curr_year][quarter][plang]["del"] += commit["deletions"]

        if not EM.DEBUG_RUN:
            await sleep(0.4)

    # Merge into main data structures
    for year, quarters in repo_yearly_data.items():
        if year not in yearly_data:
            yearly_data[year] = {}
        for quarter, languages in quarters.items():
            if quarter not in yearly_data[year]:
                yearly_data[year][quarter] = {}
            for lang, stats in languages.items():
                if lang not in yearly_data[year][quarter]:
                    yearly_data[year][quarter][lang] = {"add": 0, "del": 0}
                yearly_data[year][quarter][lang]["add"] += stats["add"]
                yearly_data[year][quarter][lang]["del"] += stats["del"]

    if repo_name not in date_data:
        date_data[repo_name] = {}
    date_data[repo_name].update(repo_date_data.get(repo_name, {}))

    # Save to cache
    cache_data = {
        "yearly_data": repo_yearly_data,
        "date_data": {repo_name: repo_date_data.get(repo_name, {})},
        "cached_at": datetime.now().isoformat(),
        "language": repo_details.get("primaryLanguage", {}).get("name") if repo_details.get("primaryLanguage") else None,
    }
    save_repo_to_cache(repo_name, cache_data, cache_index)
    DBM.g(f"\t\tSaved {repo_name} to cache")


# Keep original function for backward compatibility
async def update_data_with_commit_stats(repo_details: Dict, yearly_data: Dict, date_data: Dict):
    """Legacy function that updates data without caching."""
    owner = repo_details["owner"]["login"]
    repo_name = repo_details["name"]

    branch_data = await DM.get_remote_graphql("repo_branch_list", owner=owner, name=repo_name)
    if len(branch_data) == 0:
        DBM.w(f"\t\tBranch data not found, skipping {repo_name} repository...")
        return

    for branch in branch_data:
        DBM.i(f"\t\tProcessing {repo_name} branch: {branch['name']}")
        commit_data = await DM.get_remote_graphql(
            "repo_commit_list",
            owner=owner,
            name=repo_name,
            branch=branch["name"],
            id=GHM.USER.node_id,
        )
        DBM.i(f"\t\t\tFound {len(commit_data)} commits in {repo_name} branch {branch['name']}")

        if repo_name not in date_data:
            date_data[repo_name] = dict()
        if branch["name"] not in date_data[repo_name]:
            date_data[repo_name][branch["name"]] = dict()

        for commit in commit_data:
            date = search(r"\d+-\d+-\d+", commit["committedDate"]).group()
            curr_year = datetime.fromisoformat(date).year
            quarter = (datetime.fromisoformat(date).month - 1) // 3 + 1

            date_data[repo_name][branch["name"]][commit["oid"]] = commit["committedDate"]

            if repo_details["primaryLanguage"] is not None:
                plang = repo_details["primaryLanguage"]["name"]
                if curr_year not in yearly_data:
                    yearly_data[curr_year] = dict()
                if quarter not in yearly_data[curr_year]:
                    yearly_data[curr_year][quarter] = dict()
                if plang not in yearly_data[curr_year][quarter]:
                    yearly_data[curr_year][quarter][plang] = {"add": 0, "del": 0}
                yearly_data[curr_year][quarter][plang]["add"] += commit["additions"]
                yearly_data[curr_year][quarter][plang]["del"] += commit["deletions"]

        if not EM.DEBUG_RUN:
            await sleep(0.4)
