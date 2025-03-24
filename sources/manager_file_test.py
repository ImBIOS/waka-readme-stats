import pytest
import os
import json
from unittest.mock import patch, mock_open

from manager_file import FileManager, init_localization_manager
from manager_environment import EnvironmentManager as EM


@pytest.fixture
def sample_translation_data():
    return {"en": {"Monday": "Monday", "Languages": "Languages"}, "fr": {"Monday": "Lundi", "Languages": "Langages"}}


@pytest.fixture
def setup_and_teardown():
    """Fixture to setup and teardown test environment"""
    # Create test assets directory if it doesn't exist
    if not os.path.exists(FileManager.ASSETS_DIR):
        os.makedirs(FileManager.ASSETS_DIR)

    # Reset localization dictionary before each test
    FileManager._LOCALIZATION = {}

    yield

    # Cleanup any test files created in the assets directory
    test_files = ["test_file.txt", "test_binary.pkl"]
    for file in test_files:
        file_path = os.path.join(FileManager.ASSETS_DIR, file)
        if os.path.exists(file_path):
            os.remove(file_path)

    # Reset localization dictionary after each test
    FileManager._LOCALIZATION = {}


def test_init_localization_manager(setup_and_teardown, sample_translation_data):
    """Test initialization of localization manager"""
    with patch("builtins.open", mock_open(read_data=json.dumps(sample_translation_data))):
        with patch("manager_file.load_json", return_value=sample_translation_data):
            with patch.object(EM, "LOCALE", "en"):
                init_localization_manager()
                assert FileManager._LOCALIZATION == sample_translation_data["en"]


def test_load_localization(setup_and_teardown, sample_translation_data):
    """Test loading localization from file"""
    with patch("builtins.open", mock_open(read_data=json.dumps(sample_translation_data))):
        with patch("manager_file.load_json", return_value=sample_translation_data):
            with patch.object(EM, "LOCALE", "fr"):
                FileManager.load_localization("translation.json")
                assert FileManager._LOCALIZATION == sample_translation_data["fr"]


def test_translate_string(setup_and_teardown):
    """Test translating strings"""
    FileManager._LOCALIZATION = {"Monday": "Lundi", "Languages": "Langages"}

    assert FileManager.t("Monday") == "Lundi"
    assert FileManager.t("Languages") == "Langages"


def test_translate_missing_key(setup_and_teardown):
    """Test translating with missing key raises KeyError"""
    FileManager._LOCALIZATION = {"Key1": "Value1"}

    with pytest.raises(KeyError):
        FileManager.t("NonExistentKey")


def test_write_file(setup_and_teardown):
    """Test writing content to a file"""
    test_content = "Test content"
    test_filename = "test_file.txt"

    with patch("builtins.open", mock_open()) as mock_file:
        FileManager.write_file(test_filename, test_content)
        mock_file.assert_called_once_with(test_filename, "w", encoding="utf-8")
        mock_file().write.assert_called_once_with(test_content)


def test_write_file_append(setup_and_teardown):
    """Test appending content to a file"""
    test_content = "Test append content"
    test_filename = "test_file.txt"

    with patch("builtins.open", mock_open()) as mock_file:
        FileManager.write_file(test_filename, test_content, append=True)
        mock_file.assert_called_once_with(test_filename, "a", encoding="utf-8")
        mock_file().write.assert_called_once_with(test_content)


def test_write_file_to_assets(setup_and_teardown):
    """Test writing content to a file in assets directory"""
    test_content = "Test assets content"
    test_filename = "test_file.txt"
    expected_path = os.path.join(FileManager.ASSETS_DIR, test_filename)

    with patch("builtins.open", mock_open()) as mock_file:
        FileManager.write_file(test_filename, test_content, assets=True)
        mock_file.assert_called_once_with(expected_path, "w", encoding="utf-8")
        mock_file().write.assert_called_once_with(test_content)


def test_cache_binary_write(setup_and_teardown):
    """Test writing binary data to a cache file"""
    test_content = {"key": "value"}
    test_filename = "test_binary.pkl"

    with patch("builtins.open", mock_open()) as mock_file:
        with patch("manager_file.dump_pickle") as mock_dump:
            FileManager.cache_binary(test_filename, test_content)
            mock_file.assert_called_once_with(test_filename, "wb")
            mock_dump.assert_called_once_with(test_content, mock_file())


def test_cache_binary_write_to_assets(setup_and_teardown):
    """Test writing binary data to a cache file in assets directory"""
    test_content = {"key": "value"}
    test_filename = "test_binary.pkl"
    expected_path = os.path.join(FileManager.ASSETS_DIR, test_filename)

    with patch("builtins.open", mock_open()) as mock_file:
        with patch("manager_file.dump_pickle") as mock_dump:
            FileManager.cache_binary(test_filename, test_content, assets=True)
            mock_file.assert_called_once_with(expected_path, "wb")
            mock_dump.assert_called_once_with(test_content, mock_file())


def test_cache_binary_read(setup_and_teardown):
    """Test reading binary data from a cache file"""
    test_result = {"key": "value"}
    test_filename = "test_binary.pkl"

    with patch("builtins.open", mock_open()) as mock_file:
        with patch("manager_file.load_pickle", return_value=test_result) as mock_load:
            with patch("manager_file.isfile", return_value=True):
                result = FileManager.cache_binary(test_filename)
                mock_file.assert_called_once_with(test_filename, "rb")
                mock_load.assert_called_once_with(mock_file())
                assert result == test_result


def test_cache_binary_read_from_assets(setup_and_teardown):
    """Test reading binary data from a cache file in assets directory"""
    test_result = {"key": "value"}
    test_filename = "test_binary.pkl"
    expected_path = os.path.join(FileManager.ASSETS_DIR, test_filename)

    with patch("builtins.open", mock_open()) as mock_file:
        with patch("manager_file.load_pickle", return_value=test_result) as mock_load:
            with patch("manager_file.isfile", return_value=True):
                result = FileManager.cache_binary(test_filename, assets=True)
                mock_file.assert_called_once_with(expected_path, "rb")
                mock_load.assert_called_once_with(mock_file())
                assert result == test_result


def test_cache_binary_read_nonexistent_file(setup_and_teardown):
    """Test reading binary data from a nonexistent cache file"""
    test_filename = "nonexistent_file.pkl"

    with patch("manager_file.isfile", return_value=False):
        result = FileManager.cache_binary(test_filename)
        assert result is None


def test_cache_binary_read_exception(setup_and_teardown):
    """Test handling exceptions when reading binary cache file"""
    test_filename = "test_binary.pkl"

    with patch("builtins.open", mock_open()):
        with patch("manager_file.load_pickle", side_effect=Exception("Test exception")):
            with patch("manager_file.isfile", return_value=True):
                result = FileManager.cache_binary(test_filename)
                assert result is None


def test_integration_write_and_read_file(setup_and_teardown):
    """Integration test: write content to file and read it back"""
    test_content = "Test integration content"
    test_filename = "test_file.txt"
    FileManager.write_file(test_filename, test_content)

    with open(test_filename, "r", encoding="utf-8") as file:
        content = file.read()

    assert content == test_content
    os.remove(test_filename)


def test_integration_cache_binary(setup_and_teardown):
    """Integration test: write binary data to cache and read it back"""
    test_content = {"test_key": "test_value"}
    test_filename = "test_binary.pkl"

    # Write test data
    FileManager.cache_binary(test_filename, test_content)

    # Read test data
    result = FileManager.cache_binary(test_filename)

    assert result == test_content
    os.remove(test_filename)


if __name__ == "__main__":
    pytest.main()
