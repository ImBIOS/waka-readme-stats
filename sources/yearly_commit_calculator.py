from asyncio import sleep
from datetime import datetime
from json import dumps
from re import search
from typing import Dict, Tuple, List, Optional

from manager_debug import DebugManager as DBM
from manager_download import DownloadManager as DM
from manager_environment import EnvironmentManager as EM
from manager_file import FileManager as FM
from manager_github import GitHubManager as GHM

# Try to import benchmarking utilities
try:
    from benchmarking import benchmark
except ImportError:
    # Define no-op benchmarking functions if not available
    def benchmark(name=None, metadata=None):
        def decorator(func):
            return func

        return decorator


@benchmark(name="Calculate Commit Data", metadata={"operation": "commit_processing"})
async def calculate_commit_data(repositories: Dict) -> Tuple[Dict, Dict]:
    """
    Calculate commit data by years.
    Commit data includes contribution additions and deletions in each quarter of each recorded year.

    :param repositories: user repositories info dictionary.
    :returns: Commit quarter yearly data dictionary.
    """
    DBM.i("Calculating commit data...")
    if EM.DEBUG_RUN:
        content = FM.cache_binary("commits_data.pick", assets=True)
        if content is not None:
            DBM.g("Commit data restored from cache!")
            return tuple(content)
        else:
            DBM.w("No cached commit data found, recalculating...")

    yearly_data = dict()
    date_data = dict()

    # Filter out ignored repositories
    active_repos = [repo for repo in repositories if repo["name"] not in EM.IGNORED_REPOS]

    # Use caching to only process repositories that have changed
    cached_repos, new_repos = separate_cached_and_new_repos(active_repos)

    DBM.i(f"Processing {len(cached_repos)} cached repositories and {len(new_repos)} new repositories")

    # Process cached repositories
    for ind, repo in enumerate(cached_repos):
        repo_name = "[private]" if repo["isPrivate"] else f"{repo['owner']['login']}/{repo['name']}"
        DBM.i(f"\t{ind + 1}/{len(cached_repos)} Using cached data for repo: {repo_name}")

        # Get cached commit data and update yearly and date data
        commit_cache = get_cached_commit_data(repo)
        if commit_cache:
            update_yearly_data_from_cache(commit_cache, yearly_data, date_data)

    # Process new repositories
    for ind, repo in enumerate(new_repos):
        repo_name = "[private]" if repo["isPrivate"] else f"{repo['owner']['login']}/{repo['name']}"
        DBM.i(f"\t{ind + 1}/{len(new_repos)} Retrieving new repo: {repo_name}")
        await update_data_with_commit_stats(repo, yearly_data, date_data)

    DBM.g("Commit data calculated!")

    if EM.DEBUG_RUN:
        FM.cache_binary("commits_data.pick", [yearly_data, date_data], assets=True)
        FM.write_file("commits_data.json", dumps([yearly_data, date_data]), assets=True)
        DBM.g("Commit data saved to cache!")
    return yearly_data, date_data


def separate_cached_and_new_repos(
    repositories: List[Dict],
) -> Tuple[List[Dict], List[Dict]]:
    """
    Separates repositories into cached and new based on cache status.

    Args:
        repositories: List of repository information dictionaries

    Returns:
        Tuple of (cached_repos, new_repos)
    """
    cached_repos = []
    new_repos = []

    for repo in repositories:
        # Check if we have cached data for this repository
        if GHM.CACHE and GHM.CACHE.get_cached_data(repo["name"]):
            cached_repos.append(repo)
        else:
            new_repos.append(repo)

    return cached_repos, new_repos


def get_cached_commit_data(repo: Dict) -> Optional[Dict]:
    """
    Retrieves cached commit data for a repository.

    Args:
        repo: Repository information dictionary

    Returns:
        Cached commit data or None if not available
    """
    if not GHM.CACHE:
        return None

    return GHM.CACHE.get_cached_data(f"{repo['name']}_commits")


def update_yearly_data_from_cache(commit_cache: Dict, yearly_data: Dict, date_data: Dict) -> None:
    """
    Updates yearly data dictionaries from cached commit data.

    Args:
        commit_cache: Cached commit data
        yearly_data: Yearly data dictionary to update
        date_data: Commit date dictionary to update
    """
    # Extract cached data
    cache_yearly = commit_cache.get("yearly_data", {})
    cache_date = commit_cache.get("date_data", {})

    # Update yearly data
    for year, quarters in cache_yearly.items():
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

    # Update date data
    for repo_name, branches in cache_date.items():
        if repo_name not in date_data:
            date_data[repo_name] = {}

        for branch_name, commits in branches.items():
            if branch_name not in date_data[repo_name]:
                date_data[repo_name][branch_name] = {}

            for commit_id, commit_date in commits.items():
                date_data[repo_name][branch_name][commit_id] = commit_date


@benchmark(name="Update Commit Stats", metadata={"operation": "repo_processing"})
async def update_data_with_commit_stats(repo_details: Dict, yearly_data: Dict, date_data: Dict):
    """
    Updates yearly commit data with commits from given repository.
    Skips update if the commit isn't related to any repository.

    :param repo_details: Dictionary with information about the given repository.
    :param yearly_data: Yearly data dictionary to update.
    :param date_data: Commit date dictionary to update.
    """
    owner = repo_details["owner"]["login"]
    branch_data = await DM.get_remote_graphql("repo_branch_list", owner=owner, name=repo_details["name"])
    if len(branch_data) == 0:
        DBM.w("\t\tBranch data not found, skipping repository...")
        return

    repo_yearly_data = {}
    repo_date_data = {}

    for branch in branch_data:
        commit_data = await DM.get_remote_graphql(
            "repo_commit_list",
            owner=owner,
            name=repo_details["name"],
            branch=branch["name"],
            id=GHM.USER.node_id,
        )

        if repo_details["name"] not in repo_date_data:
            repo_date_data[repo_details["name"]] = {}
        if branch["name"] not in repo_date_data[repo_details["name"]]:
            repo_date_data[repo_details["name"]][branch["name"]] = {}

        for commit in commit_data:
            date = search(r"\d+-\d+-\d+", commit["committedDate"]).group()
            curr_year = datetime.fromisoformat(date).year
            quarter = (datetime.fromisoformat(date).month - 1) // 3 + 1

            # Update repo-specific date data
            repo_date_data[repo_details["name"]][branch["name"]][commit["oid"]] = commit["committedDate"]

            # Update repository's yearly data
            if repo_details["primaryLanguage"] is not None:
                if curr_year not in repo_yearly_data:
                    repo_yearly_data[curr_year] = {}
                if quarter not in repo_yearly_data[curr_year]:
                    repo_yearly_data[curr_year][quarter] = {}
                if repo_details["primaryLanguage"]["name"] not in repo_yearly_data[curr_year][quarter]:
                    repo_yearly_data[curr_year][quarter][repo_details["primaryLanguage"]["name"]] = {"add": 0, "del": 0}

                repo_yearly_data[curr_year][quarter][repo_details["primaryLanguage"]["name"]]["add"] += commit["additions"]
                repo_yearly_data[curr_year][quarter][repo_details["primaryLanguage"]["name"]]["del"] += commit["deletions"]

                # Also update the main yearly data
                if curr_year not in yearly_data:
                    yearly_data[curr_year] = {}
                if quarter not in yearly_data[curr_year]:
                    yearly_data[curr_year][quarter] = {}
                if repo_details["primaryLanguage"]["name"] not in yearly_data[curr_year][quarter]:
                    yearly_data[curr_year][quarter][repo_details["primaryLanguage"]["name"]] = {"add": 0, "del": 0}

                yearly_data[curr_year][quarter][repo_details["primaryLanguage"]["name"]]["add"] += commit["additions"]
                yearly_data[curr_year][quarter][repo_details["primaryLanguage"]["name"]]["del"] += commit["deletions"]

            # Update main date data
            if repo_details["name"] not in date_data:
                date_data[repo_details["name"]] = {}
            if branch["name"] not in date_data[repo_details["name"]]:
                date_data[repo_details["name"]][branch["name"]] = {}
            date_data[repo_details["name"]][branch["name"]][commit["oid"]] = commit["committedDate"]

        if not EM.DEBUG_RUN:
            await sleep(0.4)

    # Cache the repository's commit data
    if GHM.CACHE:
        cache_data = {"yearly_data": repo_yearly_data, "date_data": repo_date_data}
        GHM.CACHE.update_cache(f"{repo_details['name']}_commits", cache_data)
