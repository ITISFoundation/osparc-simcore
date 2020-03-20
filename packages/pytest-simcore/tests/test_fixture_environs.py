import sys
from pathlib import Path

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

repo_base_dir = current_dir.parent.parent.parent
assert any(repo_base_dir.glob(".git"))


def test_root_dir_with_installed_plugin(testdir):
    """ Make sure osparc_simcore_root_dir is correct
        even when pytest-simcore installed
    """

    # create a temporary pytest test module
    testdir.makepyfile(
        f"""
        pytest_plugins = ["pytest_simcore.environs"]

        def test_sth(osparc_simcore_root_dir):
            assert osparc_simcore_root_dir == {repo_base_dir}
        """
    )

    result = testdir.runpytest("-v")
    # fnmatch_lines does an assertion internally
    # WARNING: this does not work with pytest-sugar!
    result.stdout.fnmatch_lines(
        ["*::test_sth PASSED*",]
    )

    # make sure that that we get a '0' exit code for the testsuite
    assert result.ret == 0
