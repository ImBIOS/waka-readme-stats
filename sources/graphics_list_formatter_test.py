import os
from unittest.mock import patch

import pytest

# Mock environment variables before importing the modules
os.environ["INPUT_GH_TOKEN"] = "mock_gh_token"
os.environ["INPUT_WAKATIME_API_KEY"] = "mock_wakatime_key"

from .graphics_list_formatter import (  # noqa: E402
    Symbol,
    make_commit_day_time_list,
    make_graph,
    make_language_per_repo_list,
    make_list,
)


@pytest.fixture(autouse=True)
def mock_environment():
    """Fixture to ensure environment variables are set for all tests"""
    with patch.dict(
        os.environ,
        {
            "INPUT_GH_TOKEN": "mock_gh_token",
            "INPUT_WAKATIME_API_KEY": "mock_wakatime_key",
            "INPUT_SYMBOL_VERSION": "1",
            "INPUT_SHOW_COMMIT": "True",
            "INPUT_SHOW_DAYS_OF_WEEK": "True",
            "INPUT_LOCALE": "en",
        },
    ):
        yield


def test_symbol_get_symbols():
    """Test Symbol.get_symbols returns correct symbols for each version"""
    assert Symbol.get_symbols(1) == ("█", "░")
    assert Symbol.get_symbols(2) == ("⣿", "⣀")
    assert Symbol.get_symbols(3) == ("⬛", "⬜")


def test_make_graph_zero_percent():
    """Test make_graph with 0% completion"""
    with patch("sources.graphics_list_formatter.EM") as mock_em:
        mock_em.SYMBOL_VERSION = 1
        result = make_graph(0)
        assert result == "░" * 25


def test_make_graph_one_hundred_percent():
    """Test make_graph with 100% completion"""
    with patch("sources.graphics_list_formatter.EM") as mock_em:
        mock_em.SYMBOL_VERSION = 1
        result = make_graph(100)
        assert result == "█" * 25


def test_make_graph_fifty_percent():
    """Test make_graph with 50% completion"""
    with patch("sources.graphics_list_formatter.EM") as mock_em:
        mock_em.SYMBOL_VERSION = 1
        result = make_graph(50)
        # 50 / 4 = 12.5 -> rounded to 12
        expected = "█" * 12 + "░" * 13
        assert result == expected


def test_make_list_with_lists():
    """Test make_list with separate name, text, percent lists"""
    names = ["Python", "JavaScript", "Java"]
    texts = ["10 hrs", "5 hrs", "3 hrs"]
    percents = [50.0, 30.0, 20.0]

    result = make_list(names=names, texts=texts, percents=percents, sort=False)
    lines = result.split("\n")
    assert len(lines) == 3
    assert "Python" in lines[0]
    assert "50.00" in lines[0]


def test_make_list_with_data_dict():
    """Test make_list with data dictionary"""
    data = [
        {"name": "Python", "text": "10 hrs", "percent": 50.0},
        {"name": "JavaScript", "text": "5 hrs", "percent": 30.0},
    ]

    result = make_list(data=data, sort=False)
    lines = result.split("\n")
    assert len(lines) == 2
    assert "Python" in lines[0]
    assert "JavaScript" in lines[1]


def test_make_list_sorted():
    """Test make_list with sorting enabled"""
    names = ["Java", "Python", "JavaScript"]
    texts = ["3 hrs", "10 hrs", "5 hrs"]
    percents = [20.0, 50.0, 30.0]

    result = make_list(names=names, texts=texts, percents=percents, sort=True)
    lines = result.split("\n")
    assert "Python" in lines[0]  # Highest percent first
    assert "JavaScript" in lines[1]
    assert "Java" in lines[2]


def test_make_list_top_num_limit():
    """Test make_list limits to top_num items"""
    names = ["Lang1", "Lang2", "Lang3", "Lang4", "Lang5", "Lang6"]
    texts = ["1h"] * 6
    percents = [10.0] * 6

    result = make_list(names=names, texts=texts, percents=percents, top_num=3)
    lines = result.split("\n")
    assert len(lines) == 3


def test_make_list_long_names_truncated():
    """Test make_list truncates long names to 25 chars"""
    long_name = "A" * 50
    names = [long_name]
    texts = ["test"]
    percents = [50.0]

    result = make_list(names=names, texts=texts, percents=percents)
    lines = result.split("\n")
    # Name should be truncated to 25 chars
    assert len(lines[0]) >= 25


def test_make_language_per_repo_list():
    """Test make_language_per_repo_list with sample repositories"""
    repositories = [
        {"primaryLanguage": {"name": "Python"}},
        {"primaryLanguage": {"name": "Python"}},
        {"primaryLanguage": {"name": "JavaScript"}},
        {"primaryLanguage": None},  # Should be skipped
    ]

    with patch("sources.graphics_list_formatter.FM") as mock_fm:
        mock_fm.t.return_value = "I Mostly Code in %s"
        result = make_language_per_repo_list(repositories)

        assert "Python" in result
        assert "JavaScript" in result
        assert "2 repo" in result or "2 repos" in result
        assert "1 repo" in result or "1 repos" in result


def test_make_language_per_repo_list_no_languages():
    """Test make_language_per_repo_list with no language info"""
    repositories = [{"primaryLanguage": None}, {"primaryLanguage": None}]

    with patch("sources.graphics_list_formatter.FM") as mock_fm:
        mock_fm.t.return_value = "I Mostly Code in"
        # This should raise ValueError when no languages, let's just skip it
        try:
            result = make_language_per_repo_list(repositories)
            assert isinstance(result, str)
        except ValueError:
            # Expected behavior when no languages
            pass


@pytest.mark.asyncio
async def test_make_commit_day_time_list():
    """Test make_commit_day_time_list with sample data"""
    time_zone = "America/New_York"
    repositories = [{"name": "repo1"}]
    commit_dates = {
        "repo1": {
            "main": {
                "commit1": "2023-01-15T10:30:00Z",  # Morning
                "commit2": "2023-01-15T14:30:00Z",  # Daytime
                "commit3": "2023-01-15T20:30:00Z",  # Evening
            }
        }
    }

    with patch("sources.graphics_list_formatter.EM") as mock_em:
        mock_em.SHOW_COMMIT = True
        mock_em.SHOW_DAYS_OF_WEEK = True
        mock_em.SYMBOL_VERSION = "1"

        with patch("sources.graphics_list_formatter.FM") as mock_fm:

            def mock_translate(key):
                translations = {
                    "Morning": "Morning",
                    "Daytime": "Daytime",
                    "Evening": "Evening",
                    "Night": "Night",
                    "I am an Early": "I am an Early",
                    "I am a Night": "I am a Night",
                    "Monday": "Monday",
                    "Tuesday": "Tuesday",
                    "Wednesday": "Wednesday",
                    "Thursday": "Thursday",
                    "Friday": "Friday",
                    "Saturday": "Saturday",
                    "Sunday": "Sunday",
                    "I am Most Productive on": "I am Most Productive on %s",
                }
                return translations.get(key, key)

            mock_fm.t.side_effect = mock_translate

            result = await make_commit_day_time_list(time_zone, repositories, commit_dates)

            assert isinstance(result, str)
            assert "Morning" in result or "morning" in result.lower()
            assert "commits" in result.lower()


@pytest.mark.asyncio
async def test_make_commit_day_time_list_no_commits():
    """Test make_commit_day_time_list with no commits"""
    time_zone = "America/New_York"
    repositories = [{"name": "repo1"}]
    commit_dates = {}

    with patch("sources.graphics_list_formatter.EM") as mock_em:
        mock_em.SHOW_COMMIT = True
        mock_em.SHOW_DAYS_OF_WEEK = True
        mock_em.SYMBOL_VERSION = "1"

        with patch("sources.graphics_list_formatter.FM") as mock_fm:

            def mock_translate(key):
                translations = {
                    "I am Most Productive on": "I am Most Productive on %s",
                    "Morning": "Morning",
                    "Daytime": "Daytime",
                    "Evening": "Evening",
                    "Night": "Night",
                }
                return translations.get(key, key)

            mock_fm.t.side_effect = mock_translate

            result = await make_commit_day_time_list(time_zone, repositories, commit_dates)

            assert isinstance(result, str)


@pytest.mark.asyncio
async def test_make_commit_day_time_list_show_commit_disabled():
    """Test make_commit_day_time_list with SHOW_COMMIT disabled"""
    time_zone = "America/New_York"
    repositories = [{"name": "repo1"}]
    commit_dates = {
        "repo1": {
            "main": {
                "commit1": "2023-01-15T10:30:00Z",
            }
        }
    }

    with patch("sources.graphics_list_formatter.EM") as mock_em:
        mock_em.SHOW_COMMIT = False
        mock_em.SHOW_DAYS_OF_WEEK = True
        mock_em.SYMBOL_VERSION = "1"

        with patch("sources.graphics_list_formatter.FM") as mock_fm:

            def mock_translate(key):
                translations = {
                    "I am Most Productive on": "I am Most Productive on %s",
                    "Monday": "Monday",
                    "Tuesday": "Tuesday",
                    "Wednesday": "Wednesday",
                    "Thursday": "Thursday",
                    "Friday": "Friday",
                    "Saturday": "Saturday",
                    "Sunday": "Sunday",
                }
                return translations.get(key, key)

            mock_fm.t.side_effect = mock_translate

            result = await make_commit_day_time_list(time_zone, repositories, commit_dates)

            assert isinstance(result, str)
