import asyncio
import logging
import os
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
import yaml
from httpx import AsyncClient

# Mock environment variables before importing the modules
os.environ["INPUT_GH_TOKEN"] = "mock_gh_token"
os.environ["INPUT_WAKATIME_API_KEY"] = "mock_wakatime_key"
os.environ["GH_PAT"] = "mock_gh_pat"
os.environ["DEBUG"] = "true"
os.environ["INPUT_SHOW_TITLE"] = "false"
os.environ["INPUT_BLOCKS"] = "░▒▓█"
os.environ["INPUT_TIME_RANGE"] = "all_time"
os.environ["INPUT_SHOW_TIME"] = "true"
os.environ["INPUT_SHOW_MASKED_TIME"] = "false"
os.environ["INPUT_SYMBOL_VERSION"] = "1"

from manager_debug import DebugManager

# Now we can safely import the modules
from manager_download import DownloadManager, init_download_manager

# Initialize DebugManager logger
DebugManager._logger = logging.getLogger("test")
DebugManager._logger.addHandler(logging.NullHandler())


@pytest_asyncio.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_client():
    """Setup and cleanup AsyncClient for each test"""
    try:
        async with AsyncClient(timeout=5.0) as client:
            DownloadManager._client = client
            yield
    finally:
        # Proper cleanup
        if hasattr(DownloadManager, "_client"):
            if not DownloadManager._client.is_closed:
                await DownloadManager._client.aclose()
        DownloadManager._REMOTE_RESOURCES_CACHE.clear()


@pytest_asyncio.fixture
async def mock_client():
    """Fixture to create a mock AsyncClient"""
    with patch("manager_download.AsyncClient") as mock:
        client = AsyncMock()
        client.post.return_value = AsyncMock(
            status_code=200,
            json=lambda: {"data": {}},
            __aenter__=AsyncMock(
                return_value=AsyncMock(status_code=200, json=lambda: {"data": {}})
            ),
            __aexit__=AsyncMock(),
        )
        client.get.return_value = AsyncMock(
            status_code=200,
            json=lambda: {"data": {}},
            __aenter__=AsyncMock(
                return_value=AsyncMock(status_code=200, json=lambda: {"data": {}})
            ),
            __aexit__=AsyncMock(),
        )
        mock.return_value = client
        DownloadManager._client = client
        yield client


@pytest.fixture(autouse=True)
def mock_environment():
    """Fixture to ensure environment variables are set for all tests"""
    with patch.dict(
        os.environ,
        {
            "INPUT_GH_TOKEN": "mock_gh_token",
            "INPUT_WAKATIME_API_KEY": "mock_wakatime_key",
            "GH_PAT": "mock_gh_pat",
            "DEBUG": "true",
            "INPUT_SHOW_TITLE": "false",
            "INPUT_BLOCKS": "░▒▓█",
            "INPUT_TIME_RANGE": "all_time",
            "INPUT_SHOW_TIME": "true",
            "INPUT_SHOW_MASKED_TIME": "false",
            "INPUT_SYMBOL_VERSION": "1",
        },
    ):
        yield


@pytest_asyncio.fixture
async def mock_client():
    """Fixture to create a mock AsyncClient"""
    with patch("manager_download.AsyncClient") as mock:
        client = AsyncMock()
        client.post.return_value = AsyncMock(
            status_code=200,
            json=lambda: {"data": {}},
            __aenter__=AsyncMock(
                return_value=AsyncMock(status_code=200, json=lambda: {"data": {}})
            ),
            __aexit__=AsyncMock(),
        )
        client.get.return_value = AsyncMock(
            status_code=200,
            json=lambda: {"data": {}},
            __aenter__=AsyncMock(
                return_value=AsyncMock(status_code=200, json=lambda: {"data": {}})
            ),
            __aexit__=AsyncMock(),
        )
        mock.return_value = client
        DownloadManager._client = client
        yield client


@pytest.fixture
def sample_linguist_data():
    return {
        "Python": {
            "type": "programming",
            "color": "#3572A5",
        }
    }


@pytest.fixture
def sample_github_stats():
    return {"totalContributions": 1000, "contributions": []}


@pytest.fixture
def sample_wakatime_data():
    return {
        "data": {
            "total_seconds": 360000,
            "languages": [{"name": "Python", "total_seconds": 180000}],
        }
    }


@pytest.mark.asyncio
async def test_init_download_manager(mock_client):
    """Test initialization of download manager"""
    # Arrange
    user_login = "test_user"
    mock_response = AsyncMock(status_code=200, json=lambda: {"data": "test"})
    mock_client.get.return_value = mock_response

    # Act
    await init_download_manager(user_login)

    # Assert
    assert mock_client.get.call_count == 4
    await DownloadManager.close_remote_resources()


@pytest.mark.asyncio
async def test_load_remote_resources(mock_client):
    """Test loading remote resources"""
    # Arrange
    resources = {"test_resource": "http://test.com/api"}
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": "test"}
    mock_client.get.return_value = mock_response

    try:
        # Act
        await DownloadManager.load_remote_resources(**resources)

        # Assert
        assert "test_resource" in DownloadManager._REMOTE_RESOURCES_CACHE
        mock_client.get.assert_called_once_with("http://test.com/api")

    finally:
        # Clean up
        DownloadManager._REMOTE_RESOURCES_CACHE.clear()


@pytest.mark.asyncio
async def test_get_remote_json_success(mock_client):
    """Test successful JSON resource retrieval"""
    # Arrange
    test_data = {"key": "value"}
    mock_response = AsyncMock(status_code=200, json=lambda: test_data)
    mock_client.get.return_value = mock_response

    # Act
    await DownloadManager.load_remote_resources(test="http://test.com")
    result = await DownloadManager.get_remote_json("test")

    # Assert
    assert result == test_data
    mock_client.get.assert_called_once()


@pytest.mark.asyncio
async def test_get_remote_yaml_success(mock_client):
    """Test successful YAML resource retrieval"""
    # Arrange
    test_data = {"key": "value"}
    mock_response = AsyncMock(status_code=200, content=yaml.dump(test_data).encode())
    mock_client.get.return_value = mock_response

    await DownloadManager.load_remote_resources(test="http://test.com")

    # Act
    result = await DownloadManager.get_remote_yaml("test")

    # Assert
    assert result == test_data


@pytest.mark.asyncio
async def test_get_remote_resource_failed_status(mock_client):
    """Test handling of failed status codes"""
    # Arrange
    mock_response = AsyncMock(status_code=404, json=lambda: {"error": "Not found"})
    mock_client.get.return_value = mock_response

    await DownloadManager.load_remote_resources(test="http://test.com")

    # Act & Assert
    with pytest.raises(Exception) as exc_info:
        await DownloadManager.get_remote_json("test")
    assert "failed to run" in str(exc_info.value)


@pytest.mark.asyncio
async def test_fetch_graphql_query_success(mock_client):
    """Test successful GraphQL query"""
    # Arrange
    test_data = {"data": {"repository": {"name": "test-repo"}}}
    mock_client.post.return_value = AsyncMock(status_code=200, json=lambda: test_data)

    # Act
    result = await DownloadManager._fetch_graphql_query(
        "repo_branch_list",
        owner="test_owner",
        name="test_repo",
        pagination="first: 100",
    )

    # Assert
    assert result == test_data
    mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_graphql_paginated(mock_client):
    """Test paginated GraphQL query"""
    # Arrange
    first_page = {
        "data": {
            "repository": {
                "refs": {
                    "nodes": [{"name": "main"}],
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                }
            }
        }
    }
    mock_client.post.return_value = AsyncMock(status_code=200, json=lambda: first_page)

    # Act
    result = await DownloadManager._fetch_graphql_paginated(
        "repo_branch_list", owner="test_owner", name="test_repo"
    )

    # Assert
    assert len(result) == 1
    assert result[0]["name"] == "main"
    assert mock_client.post.call_count == 1


@pytest.mark.asyncio
async def test_get_remote_graphql_cached(mock_client):
    """Test GraphQL query caching"""
    # Arrange
    test_data = {"data": {"repository": {"name": "test-repo"}}}
    mock_response = AsyncMock(status_code=200, json=lambda: test_data)
    mock_client.post.return_value = mock_response

    # Act
    result1 = await DownloadManager.get_remote_graphql(
        "repo_branch_list", owner="test_owner", name="test_repo"
    )
    result2 = await DownloadManager.get_remote_graphql(
        "repo_branch_list", owner="test_owner", name="test_repo"
    )

    # Assert
    assert result1 == result2
    assert mock_client.post.call_count == 1  # Should only make one API call


@pytest.mark.asyncio
async def test_close_remote_resources():
    """Test closing remote resources"""
    # Arrange
    mock_task = AsyncMock(spec=asyncio.Task)
    mock_awaitable = AsyncMock()
    mock_awaitable.__await__ = AsyncMock(
        return_value=iter([None])
    )  # Make it properly awaitable

    # Configure mock task
    mock_task.done.return_value = False
    mock_task.cancelled.return_value = False
    mock_task.cancel = AsyncMock()

    # Store original cache
    original_cache = DownloadManager._REMOTE_RESOURCES_CACHE.copy()

    try:
        # Set up the cache with our mocks
        DownloadManager._REMOTE_RESOURCES_CACHE = {
            "test_task": mock_task,
            "test_awaitable": mock_awaitable,
        }

        # Act
        await DownloadManager.close_remote_resources()

        # Assert
        mock_task.cancel.assert_called_once()
        # No need to await mock_awaitable as it's handled in close_remote_resources

    finally:
        # Restore original cache
        DownloadManager._REMOTE_RESOURCES_CACHE = original_cache


# Additional helper tests
def test_find_pagination_and_data_list():
    """Test pagination data extraction"""
    # Test nested structure
    nested_response = {
        "user": {
            "repositories": {
                "nodes": [{"name": "repo1"}],
                "pageInfo": {"hasNextPage": False},
            }
        }
    }
    nodes, page_info = DownloadManager._find_pagination_and_data_list(nested_response)
    assert len(nodes) == 1
    assert nodes[0]["name"] == "repo1"
    assert page_info["hasNextPage"] is False

    # Test direct structure
    direct_response = {"nodes": [{"name": "repo2"}], "pageInfo": {"hasNextPage": True}}
    nodes, page_info = DownloadManager._find_pagination_and_data_list(direct_response)
    assert len(nodes) == 1
    assert nodes[0]["name"] == "repo2"
    assert page_info["hasNextPage"] is True

    # Test invalid structure
    invalid_response = {"key": "value"}
    nodes, page_info = DownloadManager._find_pagination_and_data_list(invalid_response)
    assert len(nodes) == 0
    assert page_info["hasNextPage"] is False


@pytest.mark.asyncio
async def test_retry_on_502_error(mock_client):
    """Test retry behavior on 502 error"""
    # Arrange
    test_data = {"data": {"repository": {"name": "test-repo"}}}
    mock_502_response = AsyncMock(
        status_code=502, json=lambda: {"error": "Bad Gateway"}
    )
    mock_success_response = AsyncMock(status_code=200, json=lambda: test_data)

    mock_client.post.side_effect = [mock_502_response, mock_success_response]

    # Act
    result = await DownloadManager._fetch_graphql_query(
        "repo_branch_list",
        retries_count=1,
        owner="test_owner",
        name="test_repo",
        pagination="first: 100",
    )

    # Assert
    assert result == test_data
    assert (
        mock_client.post.call_count == 2
    )  # Should make two calls: one failed, one successful


@pytest.mark.asyncio
async def test_accepted_status_codes(mock_client):
    """Test handling of 201 and 202 status codes"""
    # Test 201 status code
    mock_client.get.return_value = AsyncMock(status_code=201)
    await DownloadManager.load_remote_resources(test_201="http://test.com/201")
    result_201 = await DownloadManager.get_remote_json("test_201")
    assert result_201 is None

    # Test 202 status code
    mock_client.get.return_value = AsyncMock(status_code=202)
    await DownloadManager.load_remote_resources(test_202="http://test.com/202")
    result_202 = await DownloadManager.get_remote_json("test_202")
    assert result_202 is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
