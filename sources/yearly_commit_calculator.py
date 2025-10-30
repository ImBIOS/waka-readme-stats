from asyncio import Semaphore, gather, sleep
from datetime import datetime
from json import dumps
from os import cpu_count, getenv
from re import search
from typing import Dict, Tuple

from manager_debug import DebugManager as DBM
from manager_download import DownloadManager as DM
from manager_environment import EnvironmentManager as EM
from manager_file import FileManager as FM
from manager_github import GitHubManager as GHM


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

    # Determine concurrency
    configured = getenv("INPUT_MAX_CONCURRENCY", "")
    try:
        max_concurrency = int(configured) if configured else 0
    except ValueError:
        max_concurrency = 0
    if max_concurrency <= 0:
        cores = cpu_count() or 4
        # Reasonable default to avoid API abuse while using cores
        max_concurrency = max(2, min(cores, 16))

    sem = Semaphore(max_concurrency)

    async def process_one(index: int, repo: Dict) -> None:
        if repo["name"] in EM.IGNORED_REPOS:
            return
        repo_name = "[private]" if repo["isPrivate"] else f"{repo['owner']['login']}/{repo['name']}"
        DBM.i(f"\t{index + 1}/{len(repositories)} Retrieving repo: {repo_name}")
        async with sem:
            await update_data_with_commit_stats(repo, yearly_data, date_data)

    tasks = [process_one(ind, repo) for ind, repo in enumerate(repositories)]
    DBM.i(f"Processing {len(repositories)} repositories...")
    if tasks:
        await gather(*tasks)
    DBM.g("Commit data calculated!")

    if EM.DEBUG_RUN:
        FM.cache_binary("commits_data.pick", [yearly_data, date_data], assets=True)
        FM.write_file("commits_data.json", dumps([yearly_data, date_data]), assets=True)
        DBM.g("Commit data saved to cache!")
    return yearly_data, date_data


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
        DBM.w("\t\tBranch data not found, skipping {repo_details['name']} repository...")
        return

    for branch in branch_data:
        DBM.i(f"\t\tProcessing {repo_details['name']} branch: {branch['name']}")
        commit_data = await DM.get_remote_graphql(
            "repo_commit_list",
            owner=owner,
            name=repo_details["name"],
            branch=branch["name"],
            id=GHM.USER.node_id,
        )
        DBM.i(f"\t\t\tFound {len(commit_data)} commits in {repo_details['name']} branch {branch['name']}")
        for commit in commit_data:
            date = search(r"\d+-\d+-\d+", commit["committedDate"]).group()
            curr_year = datetime.fromisoformat(date).year
            quarter = (datetime.fromisoformat(date).month - 1) // 3 + 1

            if repo_details["name"] not in date_data:
                DBM.i(f"\t\t\tInitializing date_data for repo {repo_details['name']}")
                date_data[repo_details["name"]] = dict()
            if branch["name"] not in date_data[repo_details["name"]]:
                DBM.i(f"\t\t\tInitializing date_data for branch {branch['name']}")
                date_data[repo_details["name"]][branch["name"]] = dict()
            date_data[repo_details["name"]][branch["name"]][commit["oid"]] = commit["committedDate"]
            DBM.i(f"\t\t\tProcessed commit {commit['oid']} on {commit['committedDate']} " f"(+{commit['additions']}/-{commit['deletions']})")

            if repo_details["primaryLanguage"] is not None:
                plang = repo_details["primaryLanguage"]["name"]
                if curr_year not in yearly_data:
                    DBM.i(f"\t\t\tInitializing yearly_data for year {curr_year}")
                    yearly_data[curr_year] = dict()
                if quarter not in yearly_data[curr_year]:
                    DBM.i(f"\t\t\tInitializing yearly_data for year {curr_year} Q{quarter}")
                    yearly_data[curr_year][quarter] = dict()
                if plang not in yearly_data[curr_year][quarter]:
                    DBM.i(f"\t\t\tInitializing yearly_data for language {plang} in year {curr_year} Q{quarter}")
                    yearly_data[curr_year][quarter][plang] = {"add": 0, "del": 0}
                yearly_data[curr_year][quarter][plang]["add"] += commit["additions"]
                yearly_data[curr_year][quarter][plang]["del"] += commit["deletions"]
                DBM.i(
                    f"\t\t\tUpdated yearly_data[{curr_year}][{quarter}][{plang}] "
                    f"to add={yearly_data[curr_year][quarter][plang]['add']} del={yearly_data[curr_year][quarter][plang]['del']}"
                )

        if not EM.DEBUG_RUN:
            await sleep(0.4)
