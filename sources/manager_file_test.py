import json
import os
import pickle
from unittest.mock import mock_open, patch

import pytest

# Mock environment variables before importing the modules
os.environ["INPUT_GH_TOKEN"] = "mock_gh_token"
os.environ["INPUT_WAKATIME_API_KEY"] = "mock_wakatime_key"

from .manager_file import FileManager, init_localization_manager  # noqa: E402


@pytest.fixture(autouse=True)
def mock_environment():
    """Fixture to ensure environment variables are set for all tests"""
    with patch.dict(
        os.environ,
        {
            "INPUT_GH_TOKEN": "mock_gh_token",
            "INPUT_WAKATIME_API_KEY": "mock_wakatime_key",
            "INPUT_LOCALE": "en",
        },
    ):
        yield


def test_load_localization():
    """Test loading localization file"""
    mock_translation = {"en": {"test": "Test translation"}}

    with patch("builtins.open", mock_open(read_data=json.dumps(mock_translation))):
        FileManager.load_localization("translation.json")
        assert FileManager._LOCALIZATION == {"test": "Test translation"}


def test_translate_key():
    """Test translating a key"""
    FileManager._LOCALIZATION = {"hello": "Hello", "world": "World"}
    assert FileManager.t("hello") == "Hello"
    assert FileManager.t("world") == "World"


def test_write_file_new(tmp_path):
    """Test writing a new file"""
    test_file = tmp_path / "test.txt"
    FileManager.write_file(str(test_file), "Hello World")
    assert test_file.read_text(encoding="utf-8") == "Hello World"


def test_write_file_append(tmp_path):
    """Test appending to a file"""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello", encoding="utf-8")
    FileManager.write_file(str(test_file), " World", append=True)
    assert test_file.read_text(encoding="utf-8") == "Hello World"


def test_write_file_with_assets(tmp_path):
    """Test writing to assets directory"""
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()

    with patch("sources.manager_file.FileManager.ASSETS_DIR", str(assets_dir)):
        FileManager.write_file("test.txt", "Content", assets=True)
        assert (assets_dir / "test.txt").exists()
        assert (assets_dir / "test.txt").read_text(encoding="utf-8") == "Content"


def test_cache_binary_write(tmp_path):
    """Test caching binary data"""
    test_file = tmp_path / "cache.pick"
    test_data = {"key": "value"}

    FileManager.cache_binary(str(test_file), test_data)
    assert test_file.exists()

    # Verify data can be read back
    loaded_data = FileManager.cache_binary(str(test_file))
    assert loaded_data == test_data


def test_cache_binary_read_missing_file(tmp_path):
    """Test reading cache when file doesn't exist"""
    test_file = tmp_path / "nonexistent.pick"
    result = FileManager.cache_binary(str(test_file))
    assert result is None


def test_cache_binary_read_existing_file(tmp_path):
    """Test reading cache from existing file"""
    test_file = tmp_path / "cache.pick"
    test_data = {"key": "value"}

    # Write data directly
    with open(test_file, "wb") as f:
        pickle.dump(test_data, f)

    # Read using cache_binary
    loaded_data = FileManager.cache_binary(str(test_file))
    assert loaded_data == test_data


def test_cache_binary_with_assets(tmp_path):
    """Test caching to assets directory"""
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()

    with patch("sources.manager_file.FileManager.ASSETS_DIR", str(assets_dir)):
        test_data = {"key": "value"}
        FileManager.cache_binary("cache.pick", test_data, assets=True)
        assert (assets_dir / "cache.pick").exists()

        loaded_data = FileManager.cache_binary("cache.pick", assets=True)
        assert loaded_data == test_data


def test_cache_binary_invalid_file(tmp_path):
    """Test reading invalid pickle file"""
    test_file = tmp_path / "invalid.pick"
    test_file.write_bytes(b"not a valid pickle")

    # Should return None for invalid pickles
    result = FileManager.cache_binary(str(test_file))
    assert result is None


def test_init_localization_manager():
    """Test init_localization_manager function"""
    mock_translation = {"en": {"test": "test"}}

    with patch("builtins.open", mock_open(read_data=json.dumps(mock_translation))):
        with patch("sources.manager_file.EM") as mock_em:
            mock_em.LOCALE = "en"
            init_localization_manager()
            assert FileManager._LOCALIZATION is not None
