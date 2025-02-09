import os
from unittest.mock import AsyncMock, patch

import pytest

# Mock environment variables before importing the modules
os.environ["INPUT_GH_TOKEN"] = "mock_gh_token"
os.environ["INPUT_WAKATIME_API_KEY"] = "mock_wakatime_key"


# Import the function and constants we're testing
from graphics_chart_drawer import MAX_LANGUAGES  # noqa: E402
from graphics_chart_drawer import GRAPH_PATH, create_loc_graph  # noqa: E402


@pytest.fixture(autouse=True)
def mock_environment():
    """Fixture to ensure environment variables are set for all tests"""
    with patch.dict(
        os.environ,
        {
            "INPUT_GH_TOKEN": "mock_gh_token",
            "INPUT_WAKATIME_API_KEY": "mock_wakatime_key",
        },
    ):
        yield


@pytest.fixture
def sample_yearly_data():
    return {
        "2022": {
            1: {
                "Python": {"add": 100, "del": 50},
                "JavaScript": {"add": 80, "del": 30},
                "Java": {"add": 60, "del": 20},
            },
            2: {
                "Python": {"add": 120, "del": 40},
                "JavaScript": {"add": 90, "del": 35},
            },
            3: {
                "Python": {"add": 150, "del": 60},
                "TypeScript": {"add": 70, "del": 25},
            },
            4: {
                "Python": {"add": 200, "del": 80},
                "Go": {"add": 100, "del": 40},
            },
        },
        "2023": {
            1: {
                "Python": {"add": 180, "del": 70},
                "Rust": {"add": 90, "del": 30},
            },
            2: {
                "Python": {"add": 160, "del": 65},
                "JavaScript": {"add": 85, "del": 25},
            },
            3: {
                "Python": {"add": 140, "del": 55},
                "TypeScript": {"add": 75, "del": 30},
            },
            4: {
                "Python": {"add": 130, "del": 50},
                "Go": {"add": 95, "del": 35},
            },
        },
    }


@pytest.fixture
def sample_colors():
    return {
        "Python": {"color": "blue"},
        "JavaScript": {"color": "yellow"},
        "Java": {"color": "red"},
        "TypeScript": {"color": "blue"},
        "Go": {"color": "cyan"},
        "Rust": {"color": "orange"},
    }


@pytest.mark.asyncio
async def test_create_loc_graph_success(sample_yearly_data, sample_colors, tmp_path):
    test_save_path = str(tmp_path / "test_graph.png")

    with patch(
        "manager_download.DownloadManager.get_remote_yaml", new_callable=AsyncMock
    ) as mock_get_yaml:
        mock_get_yaml.return_value = sample_colors

        await create_loc_graph(sample_yearly_data, test_save_path)

        assert os.path.exists(test_save_path)
        assert os.path.getsize(test_save_path) > 0


@pytest.mark.asyncio
async def test_create_loc_graph_no_colors(sample_yearly_data, tmp_path):
    test_save_path = str(tmp_path / "test_graph_no_colors.png")

    with patch(
        "manager_download.DownloadManager.get_remote_yaml", new_callable=AsyncMock
    ) as mock_get_yaml:
        mock_get_yaml.return_value = None

        await create_loc_graph(sample_yearly_data, test_save_path)

        assert os.path.exists(test_save_path)
        assert os.path.getsize(test_save_path) > 0


@pytest.mark.asyncio
async def test_create_loc_graph_empty_data(tmp_path):
    test_save_path = str(tmp_path / "test_graph_empty.png")
    empty_data = {}

    with patch(
        "manager_download.DownloadManager.get_remote_yaml", new_callable=AsyncMock
    ) as mock_get_yaml:
        mock_get_yaml.return_value = {}

        await create_loc_graph(empty_data, test_save_path)

        assert os.path.exists(test_save_path)
        assert os.path.getsize(test_save_path) > 0


@pytest.mark.asyncio
async def test_create_loc_graph_single_language(tmp_path):
    test_save_path = str(tmp_path / "test_graph_single.png")
    single_lang_data = {
        "2022": {
            1: {"Python": {"add": 100, "del": 50}},
            2: {"Python": {"add": 120, "del": 40}},
            3: {"Python": {"add": 150, "del": 60}},
            4: {"Python": {"add": 200, "del": 80}},
        }
    }

    with patch(
        "manager_download.DownloadManager.get_remote_yaml", new_callable=AsyncMock
    ) as mock_get_yaml:
        mock_get_yaml.return_value = {"Python": {"color": "blue"}}

        await create_loc_graph(single_lang_data, test_save_path)

        assert os.path.exists(test_save_path)
        assert os.path.getsize(test_save_path) > 0


@pytest.mark.asyncio
async def test_create_loc_graph_max_languages(
    sample_yearly_data, sample_colors, tmp_path
):
    test_save_path = str(tmp_path / "test_graph_max.png")

    # Add more than MAX_LANGUAGES languages to test the limit
    sample_yearly_data["2022"][1].update(
        {
            "Ruby": {"add": 50, "del": 20},
            "C++": {"add": 40, "del": 15},
            "PHP": {"add": 30, "del": 10},
        }
    )

    with patch(
        "manager_download.DownloadManager.get_remote_yaml", new_callable=AsyncMock
    ) as mock_get_yaml:
        mock_get_yaml.return_value = sample_colors

        await create_loc_graph(sample_yearly_data, test_save_path)

        assert os.path.exists(test_save_path)
        assert os.path.getsize(test_save_path) > 0


def test_constants():
    assert MAX_LANGUAGES == 5
    assert GRAPH_PATH.endswith("/bar_graph.png")
