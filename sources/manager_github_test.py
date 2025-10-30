import os
from unittest.mock import MagicMock, mock_open, patch

import pytest

# Mock environment variables before importing the modules
os.environ["INPUT_GH_TOKEN"] = "mock_gh_token"
os.environ["INPUT_WAKATIME_API_KEY"] = "mock_wakatime_key"

from manager_github import GitHubManager, init_github_manager  # noqa: E402


@pytest.fixture(autouse=True)
def mock_environment():
    """Fixture to ensure environment variables are set for all tests"""
    with patch.dict(
        os.environ,
        {
            "INPUT_GH_TOKEN": "mock_gh_token",
            "INPUT_WAKATIME_API_KEY": "mock_wakatime_key",
            "INPUT_COMMIT_MESSAGE": "Test commit",
            "INPUT_COMMIT_USERNAME": "",
            "INPUT_COMMIT_EMAIL": "",
            "INPUT_COMMIT_SINGLE": "false",
            "INPUT_PULL_BRANCH_NAME": "",
            "INPUT_PUSH_BRANCH_NAME": "",
            "INPUT_SECTION_NAME": "waka",
        },
    ):
        yield


def test_init_github_manager():
    """Test init_github_manager function"""
    mock_user = MagicMock()
    mock_user.login = "testuser"
    mock_remote = MagicMock()

    with patch("manager_github.Github") as mock_github_class:
        mock_github_instance = mock_github_class.return_value
        mock_github_instance.get_user.return_value = mock_user
        mock_github_instance.get_repo.return_value = mock_remote

        with patch("manager_github.Repo") as mock_repo_class:
            mock_repo_class.clone_from.return_value

            with patch("manager_github.rmtree") as mock_rmtree:
                with patch("manager_github.DBM") as mock_dbm:
                    init_github_manager()

                    mock_rmtree.assert_called_once()
                    mock_dbm.i.assert_called_once()


def test_prepare_github_env():
    """Test prepare_github_env method"""
    mock_user = MagicMock()
    mock_user.login = "testuser"
    mock_remote = MagicMock()
    mock_remote.default_branch = "main"

    with patch("manager_github.Github") as mock_github_class:
        mock_github_instance = mock_github_class.return_value
        mock_github_instance.get_user.return_value = mock_user
        mock_github_instance.get_repo.return_value = mock_remote

        with patch("manager_github.Repo") as mock_repo_class:
            mock_repo_instance = mock_repo_class.clone_from.return_value
            mock_repo_instance.git.checkout = MagicMock()

            with patch("manager_github.rmtree"):
                with patch("manager_github.EM") as mock_em:
                    mock_em.GH_TOKEN = "test_token"
                    mock_em.COMMIT_SINGLE = False
                    mock_em.PULL_BRANCH_NAME = ""
                    mock_em.PUSH_BRANCH_NAME = ""

                    GitHubManager.prepare_github_env()

                    assert GitHubManager.USER == mock_user
                    assert GitHubManager.REMOTE == mock_remote
                    assert GitHubManager.REPO == mock_repo_instance


def test_get_author_commit_by_me():
    """Test _get_author when COMMIT_BY_ME is True"""
    mock_user = MagicMock()
    mock_user.login = "testuser"
    mock_user.email = "test@example.com"
    GitHubManager.USER = mock_user

    with patch("manager_github.EM") as mock_em:
        mock_em.COMMIT_BY_ME = True
        mock_em.COMMIT_USERNAME = "customname"
        mock_em.COMMIT_EMAIL = "custom@example.com"

        author = GitHubManager._get_author()

        assert author.name == "customname"
        assert author.email == "custom@example.com"


def test_get_author_not_by_me():
    """Test _get_author when COMMIT_BY_ME is False"""
    mock_user = MagicMock()
    mock_user.login = "testuser"
    GitHubManager.USER = mock_user

    with patch("manager_github.EM") as mock_em:
        mock_em.COMMIT_BY_ME = False
        mock_em.COMMIT_USERNAME = ""
        mock_em.COMMIT_EMAIL = ""

        author = GitHubManager._get_author()

        assert author.name == "readme-bot"
        assert author.email == "41898282+github-actions[bot]@users.noreply.github.com"


def test_branch_with_default():
    """Test branch method returning default branch"""
    mock_remote = MagicMock()
    mock_remote.default_branch = "main"
    GitHubManager.REMOTE = mock_remote

    result = GitHubManager.branch("")
    assert result == "main"


def test_branch_with_specific():
    """Test branch method returning specific branch"""
    mock_remote = MagicMock()
    mock_remote.default_branch = "main"
    GitHubManager.REMOTE = mock_remote

    result = GitHubManager.branch("develop")
    assert result == "develop"


def test_update_readme():
    """Test update_readme method"""
    mock_readme = MagicMock()
    mock_readme.path = "README.md"
    mock_remote = MagicMock()
    mock_remote.get_readme.return_value = mock_readme
    GitHubManager.REMOTE = mock_remote

    mock_repo = MagicMock()
    mock_repo.working_tree_dir = "/test/repo"
    mock_repo.git.add = MagicMock()
    GitHubManager.REPO = mock_repo

    with patch(
        "builtins.open",
        mock_open(read_data="<!--START_SECTION:waka-->\nOld content\n<!--END_SECTION:waka-->"),
    ):
        with patch("manager_github.DBM") as mock_dbm:
            GitHubManager.update_readme("New stats")

            mock_repo.git.add.assert_called_once_with("/test/repo/README.md")
            mock_dbm.g.assert_called_once()


def test_update_chart_debug_mode():
    """Test update_chart in debug mode"""
    GitHubManager.REPO = MagicMock()
    GitHubManager._REMOTE_NAME = "testuser/testuser"

    with patch("manager_github.EM") as mock_em:
        mock_em.DEBUG_RUN = True
        mock_em.PUSH_BRANCH_NAME = ""

        with patch("builtins.open", mock_open(read_data=b"fake_png_data")):
            with patch("manager_github.DBM"):
                result = GitHubManager.update_chart("Test Chart", "test.png")

                assert "base64" in result
                # Chart name is used in the output filename, not in the returned text
                assert result.startswith("You can use")


def test_update_chart_normal_mode():
    """Test update_chart in normal mode"""
    mock_repo = MagicMock()
    mock_repo.working_tree_dir = "/test/repo"
    GitHubManager.REPO = mock_repo
    GitHubManager._REMOTE_NAME = "testuser/testuser"

    with patch("manager_github.EM") as mock_em:
        mock_em.DEBUG_RUN = False
        mock_em.PUSH_BRANCH_NAME = ""

        with patch("manager_github.rmtree"):
            with patch("manager_github.copy") as mock_copy:
                with patch("manager_github.makedirs"):
                    mock_repo.git.add = MagicMock()

                    with patch("manager_github.DBM"):
                        result = GitHubManager.update_chart("Test Chart", "test.png")

                        assert "raw.githubusercontent.com" in result
                        mock_copy.assert_called_once()


def test_commit_update():
    """Test commit_update method"""
    mock_repo = MagicMock()
    mock_repo.index.commit = MagicMock()
    mock_repo.remotes.origin.push = MagicMock(return_value=[MagicMock()])
    GitHubManager.REPO = mock_repo

    with patch("manager_github.EM") as mock_em:
        mock_em.COMMIT_MESSAGE = "Test commit"
        mock_em.COMMIT_SINGLE = False
        mock_em.PUSH_BRANCH_NAME = ""

        with patch("manager_github.DBM"):
            GitHubManager.commit_update()

            mock_repo.index.commit.assert_called_once()
            mock_repo.remotes.origin.push.assert_called_once()


def test_set_github_output_with_env():
    """Test set_github_output with GITHUB_OUTPUT set"""
    with patch.dict("manager_github.environ", {"GITHUB_OUTPUT": "/tmp/output.txt"}):
        with patch("manager_github.FM") as mock_fm:
            with patch("manager_github.DBM") as mock_dbm:
                GitHubManager.set_github_output("Test stats")

                mock_fm.write_file.assert_called_once()
                mock_dbm.g.assert_called_once()


def test_set_github_output_without_env():
    """Test set_github_output without GITHUB_OUTPUT set"""
    if "GITHUB_OUTPUT" in os.environ:
        del os.environ["GITHUB_OUTPUT"]

    with patch("manager_github.DBM") as mock_dbm:
        GitHubManager.set_github_output("Test stats")

        mock_dbm.p.assert_called_once()
