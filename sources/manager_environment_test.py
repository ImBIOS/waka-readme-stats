import pytest
from .manager_environment import EnvironmentManager


@pytest.fixture
def env_manager():
    return EnvironmentManager()


def test_required_variables(env_manager):
    assert env_manager.GH_TOKEN
    assert env_manager.WAKATIME_API_KEY


def test_default_values(env_manager):
    assert env_manager.SECTION_NAME == "waka"
    assert env_manager.PULL_BRANCH_NAME == ""
    assert env_manager.PUSH_BRANCH_NAME == ""


def test_boolean_variables(env_manager):
    assert isinstance(env_manager.SHOW_OS, bool)
    assert isinstance(env_manager.SHOW_PROJECTS, bool)
    assert isinstance(env_manager.SHOW_EDITORS, bool)
    # Add similar assertions for other boolean variables


def test_list_variable(env_manager):
    assert isinstance(env_manager.IGNORED_REPOS, list)


def test_string_variable(env_manager):
    assert isinstance(env_manager.SYMBOL_VERSION, str)


def test_debugging_variables(env_manager):
    assert isinstance(env_manager.DEBUG_LOGGING, bool)
    assert isinstance(env_manager.DEBUG_RUN, bool)


# Add more tests for other attributes and functionalities as needed

if __name__ == "__main__":
    pytest.main()
