# pylint: disable=redefined-outer-name

import shutil
import subprocess
from pathlib import Path

import pytest


def _run(program: str, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    executable = shutil.which(program)
    assert executable, f"{program} not found"
    return subprocess.run(  # noqa: S603
        [executable, *args], cwd=cwd, capture_output=True, text=True, check=True
    )


@pytest.fixture
def resync_lockfiles_script(osparc_simcore_root_dir: Path) -> Path:
    return osparc_simcore_root_dir / ".github" / "renovate" / "resync-lockfiles.bash"


@pytest.fixture
def git_repo_with_lockfile(tmp_path: Path) -> Path:
    """A repository whose only pip-compile lockfile already pins virtualenv==21.14.10"""
    lockfile = tmp_path / "requirements" / "_tools.txt"
    lockfile.parent.mkdir()
    lockfile.write_text("virtualenv==21.14.10\n")
    identity = ("-c", "user.name=test", "-c", "user.email=test@example.com")
    _run("git", *identity, "init", "--quiet", cwd=tmp_path)
    _run("git", *identity, "add", ".", cwd=tmp_path)
    _run("git", *identity, "commit", "--quiet", "--message", "init", cwd=tmp_path)
    return tmp_path


def test_resync_lockfiles_propagates_only_the_highest_pin_of_a_package(
    resync_lockfiles_script: Path, git_repo_with_lockfile: Path
):
    # Renovate lists one upgrade per lockfile, so a security branch can carry the same
    # package at two versions (e.g. 21.14.9 for vulnerable lockfiles, 21.14.10 for the
    # others); passing both to uv makes every resolution unsatisfiable
    pins_file = git_repo_with_lockfile / "pins.txt"
    pins_file.write_text("virtualenv==21.14.10\nvirtualenv==21.14.9\nPyYAML==6.0.2\n")

    result = _run("bash", f"{resync_lockfiles_script}", f"{pins_file}", cwd=git_repo_with_lockfile)

    pins_line = next(line for line in result.stdout.splitlines() if line.startswith("Propagating pins:"))
    assert set(pins_line.removeprefix("Propagating pins:").split()) == {"PyYAML==6.0.2", "virtualenv==21.14.10"}
    # the lockfile already has the highest version, so nothing is regenerated
    assert "No lockfile needs regenerating" in result.stdout
