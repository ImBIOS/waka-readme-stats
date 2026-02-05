from asyncio import Task, sleep
from hashlib import md5
from json import dumps
from string import Template
from typing import Awaitable, Callable, Dict, List, Optional, Tuple

from httpx import AsyncClient
from .manager_debug import DebugManager as DBM
from .manager_environment import EnvironmentManager as EM
from yaml import safe_load

GITHUB_API_QUERIES = {
    # Query to collect info about all user repositories, including: is it a fork, name and owner login.
    # NB! Query includes information about recent repositories only (apparently, contributed within a year).
    "repos_contributed_to": """
{
    user(login: "$username") {
        repositoriesContributedTo(orderBy: {field: CREATED_AT, direction: DESC}, $pagination, includeUserRepositories: true) {
            nodes {
                primaryLanguage {
                    name
                }
                name
                owner {
                    login
                }
                isPrivate
                isFork
            }
            pageInfo {
                endCursor
                hasNextPage
            }
        }
    }
}""",
    # Query to collect info about all repositories user created or collaborated on, including: name, primary language and owner login.
    # NB! Query doesn't include information about repositories user contributed to via pull requests.
    "user_repository_list": """
{
    user(login: "$username") {
        repositories(orderBy: {field: CREATED_AT, direction: DESC}, $pagination, affiliations: [OWNER, COLLABORATOR], isFork: false) {
            nodes {
                primaryLanguage {
                    name
                }
                name
                owner {
                    login
                }
                isPrivate
            }
            pageInfo {
                endCursor
                hasNextPage
            }
        }
    }
}
""",
    # Query to collect info about branches in the given repository, including: names.
    "repo_branch_list": """
{
    repository(owner: "$owner", name: "$name") {
        refs(refPrefix: "refs/heads/", orderBy: {direction: DESC, field: TAG_COMMIT_DATE}, $pagination) {
            nodes {
                name
            }
            pageInfo {
                endCursor
                hasNextPage
            }
        }
    }
}
""",
    # Query to collect info about user commits to given repository, including: commit date, additions and deletions numbers.
    "repo_commit_list": """
{
    repository(owner: "$owner", name: "$name") {
        ref(qualifiedName: "refs/heads/$branch") {
            target {
                ... on Commit {
                    history(author: { id: "$id" }, $pagination) {
                        nodes {
                            ... on Commit {
                                additions
                                deletions
                                committedDate
                                oid
                            }
                        }
                        pageInfo {
                            endCursor
                            hasNextPage
                        }
                    }
                }
            }
        }
    }
}
""",
    # Query to hide outdated PR comment.
    "hide_outdated_comment": """
mutation {
    minimizeComment(input: {classifier: OUTDATED, subjectId: "$id"}) {
        clientMutationId
    }
}
""",
}


async def init_download_manager(user_login: str):
    """
    Initialize download manager:
    - Setup headers for GitHub GraphQL requests.
    - Launch static queries in background.

    :param user_login: GitHub user login.
    """
    await DownloadManager.load_remote_resources(
        linguist="https://cdn.jsdelivr.net/gh/github/linguist@master/lib/linguist/languages.yml",
        waka_latest=f"https://wakatime.com/api/v1/users/current/stats/last_7_days?api_key={EM.WAKATIME_API_KEY}",
        waka_all=f"https://wakatime.com/api/v1/users/current/all_time_since_today?api_key={EM.WAKATIME_API_KEY}",
        github_stats=f"https://github-contributions.vercel.app/api/v1/{user_login}",
    )


class DownloadManager:
    """
    Class for handling and caching all kinds of requests.
    There considered to be two types of queries:
    - Static queries: queries that don't require many arguments that should be executed once
      Example: queries to WakaTime API or to GitHub linguist
    - Dynamic queries: queries that require many arguments and should be executed multiple times
      Example: GraphQL queries to GitHub API
    DownloadManager launches all static queries asynchronously upon initialization and caches their results.
    It also executes dynamic queries upon request and caches result.
    """

    _client = AsyncClient(timeout=60.0)
    _REMOTE_RESOURCES_CACHE = dict()

    @staticmethod
    async def load_remote_resources(**resources: str):
        """
        Prepare DownloadManager to launch GitHub API queries and launch all static queries.
        :param resources: Static queries, formatted like "IDENTIFIER"="URL".
        """
        for resource, url in resources.items():
            DownloadManager._REMOTE_RESOURCES_CACHE[resource] = DownloadManager._client.get(url)

    @staticmethod
    async def close_remote_resources():
        """
        Close DownloadManager and cancel all un-awaited static web queries.
        Await all queries that could not be cancelled.
        """
        for resource in DownloadManager._REMOTE_RESOURCES_CACHE.values():
            if isinstance(resource, Task):
                resource.cancel()
            elif isinstance(resource, Awaitable):
                await resource

    @staticmethod
    async def _get_remote_resource(resource: str, convertor: Optional[Callable[[bytes], Dict]]) -> Dict or None:
        """
        Receive execution result of static query, wait for it if necessary.
        If the query wasn't cached previously, cache it.
        NB! Caching is done before response parsing - to throw exception on accessing cached erroneous response.
        :param resource: Static query identifier.
        :param convertor: Optional function to convert `response.contents` to dict.
            By default `response.json()` is used.
        :return: Response dictionary or None.
        """
        DBM.i(f"\tMaking a remote API query named '{resource}'...")
        if isinstance(DownloadManager._REMOTE_RESOURCES_CACHE[resource], Awaitable):
            res = await DownloadManager._REMOTE_RESOURCES_CACHE[resource]
            DownloadManager._REMOTE_RESOURCES_CACHE[resource] = res
            DBM.g(f"\tQuery '{resource}' finished, result saved!")
        else:
            res = DownloadManager._REMOTE_RESOURCES_CACHE[resource]
            DBM.g(f"\tQuery '{resource}' loaded from cache!")
        if res.status_code == 200:
            if convertor is None:
                return res.json()
            else:
                return convertor(res.content)
        elif res.status_code == 201:
            DBM.w(f"\tQuery '{resource}' returned 201 status code")
            return None
        elif res.status_code == 202:
            DBM.w(f"\tQuery '{resource}' returned 202 status code")
            return None
        else:
            raise Exception(f"Query '{res.url}' failed to run by returning code of {res.status_code}: {res.json()}")

    @staticmethod
    async def get_remote_json(resource: str) -> Dict or None:
        """
        Shortcut for `_get_remote_resource` to return JSON response data.
        :param resource: Static query identifier.
        :return: Response JSON dictionary.
        """
        return await DownloadManager._get_remote_resource(resource, None)

    @staticmethod
    async def get_remote_yaml(resource: str) -> Dict or None:
        """
        Shortcut for `_get_remote_resource` to return YAML response data.
        :param resource: Static query identifier.
        :return: Response YAML dictionary.
        """
        return await DownloadManager._get_remote_resource(resource, safe_load)

    @staticmethod
    async def fetch_graphql_query(query: str, retries_count: int = 10, **kwargs) -> Dict:
        """
        Execute GitHub GraphQL API simple query.
        :param query: Dynamic query identifier.
        :param use_github_action: Use GitHub actions bot auth token instead of current user.
        :param kwargs: Parameters for substitution of variables in dynamic query.
        :return: Response JSON dictionary.
        """
        headers = {"Authorization": f"Bearer {EM.GH_TOKEN}"}
        res = await DownloadManager._client.post(
            "https://api.github.com/graphql",
            json={"query": Template(GITHUB_API_QUERIES[query]).substitute(kwargs)},
            headers=headers,
        )

        # Handle rate limiting via HTTP headers (403 or 200 with rate limit in body)
        if res.status_code == 200:
            return res.json()
        elif res.status_code in (403, 502) and retries_count > 0:
            # Check if it's a rate limit error
            if res.status_code == 403:
                # GitHub uses 403 for rate limiting
                headers_dict = dict(res.headers)
                reset_timestamp = headers_dict.get("x-ratelimit-reset")
                if reset_timestamp:
                    from datetime import datetime
                    import time

                    wait_seconds = max(float(reset_timestamp) - time.time(), 1)
                    DBM.p(f"HTTP 403 Rate limit exceeded. Waiting {wait_seconds:.1f} seconds...")
                    await sleep(wait_seconds)
                    return await DownloadManager.fetch_graphql_query(query, retries_count - 1, **kwargs)
            # For 502 or 403 without reset info, use exponential backoff
            wait_time = 2 ** (10 - retries_count)
            DBM.p(f"Query '{query}' returned {res.status_code}. Retrying in {wait_time} seconds...")
            await sleep(wait_time)
            return await DownloadManager.fetch_graphql_query(query, retries_count - 1, **kwargs)
        else:
            raise Exception(f"Query '{query}' failed to run by returning code of {res.status_code}: {res.json()}")

    @staticmethod
    def find_pagination_and_data_list(response: Dict) -> Tuple[List, Dict]:
        """
        Parses response as a paginated response.
        NB! All paginated responses are expected to have the following structure:
        {
            ...: {
                "nodes": [],
                "pageInfo" : {}
            }
        }
        Where `...` states for any number of dictionaries containing _one single key_ only.
        If the structure of the response isn't met, a tuple of empty list and dist with only `hasNextPage=False` is returned!
        :param response: Response JSON dictionary.
        :returns: Tuple of the acquired pagination data list ("nodes" key) and pagination info dict ("pageInfo" key).
        """
        if "nodes" in response.keys() and "pageInfo" in response.keys():
            return response["nodes"], response["pageInfo"]
        elif len(response) == 1 and isinstance(response[list(response.keys())[0]], Dict):
            return DownloadManager.find_pagination_and_data_list(response[list(response.keys())[0]])
        else:
            return list(), dict(hasNextPage=False)

    @staticmethod
    async def fetch_graphql_paginated(query: str, **kwargs) -> Dict:
        """
        Execute GitHub GraphQL API paginated query.
        Queries 100 new results each time until no more results are left.
        Merges result list into single query, clears pagination-related info.
        :param query: Dynamic query identifier.
        :param use_github_action: Use GitHub actions bot auth token instead of current user.
        :param kwargs: Parameters for substitution of variables in dynamic query.
        :return: Response JSON dictionary.
        """
        from manager_debug import DebugManager as DBM
        from datetime import datetime

        async def execute_with_rate_limit_handling():
            nonlocal kwargs
            initial_query_response = await DownloadManager.fetch_graphql_query(query, **kwargs, pagination="first: 100")

            # Check for rate limit errors and handle them
            if "errors" in initial_query_response:
                errors = initial_query_response["errors"]
                for error in errors:
                    if error.get("type") == "RATE_LIMIT":
                        DBM.p(f"GitHub GraphQL API rate limit exceeded for query '{query}'!")

                        # Try to get reset time from extensions.rateLimit.resetAt
                        extensions = error.get("extensions", {})
                        rate_limit_info = extensions.get("rateLimit", {})
                        reset_at = rate_limit_info.get("resetAt")

                        if reset_at:
                            # Parse the ISO format datetime and calculate wait time
                            try:
                                reset_time = datetime.fromisoformat(reset_at.replace("Z", "+00:00"))
                                wait_seconds = max((reset_time - datetime.now()).total_seconds(), 1)
                                DBM.p(f"Rate limit will reset at {reset_at}. Waiting {wait_seconds:.1f} seconds...")
                                await sleep(wait_seconds)
                                # Retry the query after waiting
                                return await execute_with_rate_limit_handling()
                            except ValueError:
                                pass

                        # Fallback: exponential backoff if no reset time
                        DBM.p(f"Error: {error.get('message', 'No message')}")
                        for attempt in range(5):
                            wait_time = 2 ** attempt  # 1, 2, 4, 8, 16 seconds
                            DBM.p(f"Retrying in {wait_time} seconds... (attempt {attempt + 1}/5)")
                            await sleep(wait_time)
                            retry_response = await DownloadManager.fetch_graphql_query(
                                query, **kwargs, pagination="first: 100"
                            )
                            if "errors" not in retry_response or not any(
                                e.get("type") == "RATE_LIMIT" for e in retry_response.get("errors", [])
                            ):
                                return retry_response
                        raise Exception("Rate limit exceeded: all retries exhausted")
                    else:
                        DBM.p(f"GraphQL query '{query}' returned error: {error}")
            return initial_query_response

        initial_query_response = await execute_with_rate_limit_handling()

        page_list, page_info = DownloadManager.find_pagination_and_data_list(initial_query_response)
        while page_info["hasNextPage"]:
            pagination = f'first: 100, after: "{page_info["endCursor"]}"'
            query_response = await DownloadManager.fetch_graphql_query(query, **kwargs, pagination=pagination)

            # Check for rate limit errors on pagination requests too
            if "errors" in query_response:
                errors = query_response["errors"]
                for error in errors:
                    if error.get("type") == "RATE_LIMIT":
                        DBM.p(f"GitHub GraphQL API rate limit exceeded while fetching next page for '{query}'!")
                        extensions = error.get("extensions", {})
                        rate_limit_info = extensions.get("rateLimit", {})
                        reset_at = rate_limit_info.get("resetAt")

                        if reset_at:
                            try:
                                from datetime import datetime
                                reset_time = datetime.fromisoformat(reset_at.replace("Z", "+00:00"))
                                wait_seconds = max((reset_time - datetime.now()).total_seconds(), 1)
                                DBM.p(f"Rate limit will reset at {reset_at}. Waiting {wait_seconds:.1f} seconds...")
                                await sleep(wait_seconds)
                                # Retry the pagination request
                                query_response = await DownloadManager.fetch_graphql_query(query, **kwargs, pagination=pagination)
                                if "errors" in query_response:
                                    continue  # If still rate limited, outer loop will handle
                            except ValueError:
                                pass

            new_page_list, page_info = DownloadManager.find_pagination_and_data_list(query_response)
            page_list += new_page_list
        return page_list

    @staticmethod
    async def get_remote_graphql(query: str, **kwargs) -> Dict:
        """
        Execute GitHub GraphQL API query.
        The queries are defined in `GITHUB_API_QUERIES`, all parameters should be passed as kwargs.
        If the query wasn't cached previously, cache it. Cache query by its identifier + parameters hash.
        Merges paginated sub-queries if pagination is required for the query.
        Parse and return response as JSON.
        :param query: Dynamic query identifier.
        :param kwargs: Parameters for substitution of variables in dynamic query.
        :return: Response JSON dictionary.
        """
        key = f"{query}_{md5(dumps(kwargs, sort_keys=True).encode('utf-8')).digest()}"
        if key not in DownloadManager._REMOTE_RESOURCES_CACHE:
            if "$pagination" in GITHUB_API_QUERIES[query]:
                res = await DownloadManager.fetch_graphql_paginated(query, **kwargs)
            else:
                res = await DownloadManager.fetch_graphql_query(query, **kwargs)
            DownloadManager._REMOTE_RESOURCES_CACHE[key] = res
        else:
            res = DownloadManager._REMOTE_RESOURCES_CACHE[key]
        return res
