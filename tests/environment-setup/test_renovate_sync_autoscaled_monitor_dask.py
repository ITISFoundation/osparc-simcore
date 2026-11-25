# pylint: disable=redefined-outer-name

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

SIDECAR_LOCKFILE = "services/dask-sidecar/requirements/_dask-distributed.txt"
CLI_DIRECTORY = "scripts/maintenance/autoscaled-monitor"
CLI_PYPROJECT = f"{CLI_DIRECTORY}/pyproject.toml"

# Stands in for `uv add --no-sync dask[distributed]==<version>`: it rewrites the one dask
# dependency of the project uv runs in. FAKE_UV_EXIT makes it fail like a resolve that
# cannot satisfy the pin.
_FAKE_UV: Final[str] = r"""#!/bin/bash
echo "$PWD $*" >>"$FAKE_UV_CALLS"
if [[ -n "$FAKE_UV_EXIT" ]]; then
  echo "error: No solution found when resolving dependencies" >&2
  exit "$FAKE_UV_EXIT"
fi
wanted=$(echo "$*" | tr ' ' '\n' | grep -m1 '^dask\[distributed\]==' | cut -d= -f3)
[[ -n "$wanted" ]] || { echo "error: not a dask pin request: $*" >&2; exit 2; }
sed -i "s/\"dask\[distributed\]==[^\"]*\"/\"dask[distributed]==$wanted\"/" pyproject.toml
"""


def _run(
    program: str, *args: str, cwd: Path, env: dict[str, str] | None = None, check: bool = True
) -> subprocess.CompletedProcess[str]:
    executable = shutil.which(program)
    assert executable, f"{program} not found"
    return subprocess.run(  # noqa: S603
        [executable, *args], cwd=cwd, env=env, capture_output=True, text=True, check=check
    )


@pytest.fixture
def sync_script(osparc_simcore_root_dir: Path) -> Path:
    return osparc_simcore_root_dir / ".github" / "renovate" / "sync_autoscaled_monitor_dask.py"


@pytest.fixture
def fake_uv_env(tmp_path: Path) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    fake_uv = bin_dir / "uv"
    fake_uv.write_text(_FAKE_UV)
    fake_uv.chmod(0o755)
    return {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "FAKE_UV_CALLS": f"{tmp_path / 'calls'}",
    }


def _uv_calls(env: dict[str, str]) -> list[str]:
    calls = Path(env["FAKE_UV_CALLS"])
    return calls.read_text().splitlines() if calls.is_file() else []


def _git_repo(path: Path, sidecar_dask: str, cli_dask: str) -> Path:
    """A repository holding the dask-sidecar lockfile and the autoscaled-monitor CLI, the
    two files whose dask versions must stay equal"""
    sidecar = path / SIDECAR_LOCKFILE
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(f"cloudpickle==3.1.2\ndask=={sidecar_dask}\ndistributed=={sidecar_dask}\n")

    cli = path / CLI_DIRECTORY
    cli.mkdir(parents=True, exist_ok=True)
    (cli / "pyproject.toml").write_text(
        "[project]\n"
        'name = "autoscaled-monitor"\n'
        'requires-python = ">=3.14,<3.15"\n'
        "dependencies = [\n"
        '  "arrow",\n'
        '  "cloudpickle",\n'
        f'  "dask[distributed]=={cli_dask}",\n'
        '  "typer",\n'
        "]\n"
    )
    (cli / "uv.lock").write_text(f'version = 1\n\n[[package]]\nname = "dask"\nversion = "{cli_dask}"\n')

    identity = ("-c", "user.name=test", "-c", "user.email=test@example.com")
    _run("git", *identity, "init", "--quiet", cwd=path)
    _run("git", *identity, "add", ".", cwd=path)
    _run("git", *identity, "commit", "--quiet", "--message", "init", cwd=path)
    return path


def _run_sync(script: Path, repo: Path, pins: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    pins_file = repo / "pins.txt"
    pins_file.write_text(pins)
    return _run(sys.executable, f"{script}", f"{pins_file}", cwd=repo, env=env, check=False)


def test_sync_lockfiles_script_runs_before_this_one(osparc_simcore_root_dir: Path):
    # only the resync propagates a new version to every lockfile that pins it, so the
    # sidecar's dask pin is settled only once that one has run
    renovaterc = (osparc_simcore_root_dir / ".renovaterc.jsonc").read_text()
    post_upgrade = renovaterc[renovaterc.index('"postUpgradeTasks"') :]
    commands = re.findall(r'"(\./\.github/renovate/[^"]+\.py)"', post_upgrade[: post_upgrade.index("fileFilters")])
    assert commands == [
        "./.github/renovate/resync_lockfiles.py",
        "./.github/renovate/sync_autoscaled_monitor_dask.py",
    ]


def test_it_leaves_the_cli_alone_when_the_branch_updates_no_dask(
    sync_script: Path, tmp_path: Path, fake_uv_env: dict[str, str]
):
    repo = _git_repo(tmp_path / "repo", sidecar_dask="2026.11.0", cli_dask="2026.8.0")

    result = _run_sync(sync_script, repo, "faker==40.63.0\n", fake_uv_env)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _uv_calls(fake_uv_env) == [], "an unrelated branch must not carry a CLI version change"
    assert '"dask[distributed]==2026.8.0"' in (repo / CLI_PYPROJECT).read_text()


def test_it_shows_help_without_a_pins_file(sync_script: Path, tmp_path: Path):
    # someone running the script by hand gets the usage instead of a bare error
    env = {name: value for name, value in os.environ.items() if name != "RENOVATE_POST_UPGRADE_COMMAND_DATA_FILE"}

    result = _run(sys.executable, f"{sync_script}", cwd=tmp_path, env=env, check=False)

    assert result.returncode == 2
    assert result.stdout.startswith("usage:")
    assert "PINS_FILE" in result.stdout


def test_it_pins_the_cli_to_the_dask_version_the_cluster_runs(
    sync_script: Path, tmp_path: Path, fake_uv_env: dict[str, str]
):
    repo = _git_repo(tmp_path / "repo", sidecar_dask="2026.11.0", cli_dask="2026.8.0")

    result = _run_sync(sync_script, repo, "dask[distributed]==2026.11.0\n", fake_uv_env)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _uv_calls(fake_uv_env) == [f"{repo / CLI_DIRECTORY} add --no-sync dask[distributed]==2026.11.0"], (
        "uv has to run in the CLI directory, and --no-sync keeps it from building a venv"
    )
    assert '"dask[distributed]==2026.11.0"' in (repo / CLI_PYPROJECT).read_text()
    assert not (repo / "renovate-resync-report.md").exists()


def test_it_runs_no_uv_when_the_cli_already_follows_the_cluster(
    sync_script: Path, tmp_path: Path, fake_uv_env: dict[str, str]
):
    repo = _git_repo(tmp_path / "repo", sidecar_dask="2026.11.0", cli_dask="2026.11.0")

    result = _run_sync(sync_script, repo, "dask==2026.11.0\n", fake_uv_env)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _uv_calls(fake_uv_env) == []
    assert "already pins dask 2026.11.0" in result.stdout


def test_it_writes_the_dask_version_of_the_sidecar_lockfile_and_not_the_one_of_the_branch(
    sync_script: Path, tmp_path: Path, fake_uv_env: dict[str, str]
):
    # what the cluster runs is what the sidecar lockfile ended up holding, which the
    # resync may have left below the version Renovate asked for
    repo = _git_repo(tmp_path / "repo", sidecar_dask="2026.10.0", cli_dask="2026.8.0")

    result = _run_sync(sync_script, repo, "dask==2026.11.0\n", fake_uv_env)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _uv_calls(fake_uv_env) == [f"{repo / CLI_DIRECTORY} add --no-sync dask[distributed]==2026.10.0"]


def test_a_failed_sync_goes_to_the_pull_request_instead_of_failing_the_branch(
    sync_script: Path, tmp_path: Path, fake_uv_env: dict[str, str]
):
    repo = _git_repo(tmp_path / "repo", sidecar_dask="2026.11.0", cli_dask="2026.8.0")
    env = {**fake_uv_env, "FAKE_UV_EXIT": "1"}

    result = _run_sync(sync_script, repo, "dask==2026.11.0\n", env)

    assert result.returncode == 0, result.stdout + result.stderr
    report = repo / "renovate-resync-report.md"
    assert report.is_file()
    assert "2026.11.0" in report.read_text()
    assert "No solution found" in report.read_text()


def test_it_reports_when_the_resync_left_the_sidecar_lockfile_without_dask(
    sync_script: Path, tmp_path: Path, fake_uv_env: dict[str, str]
):
    repo = _git_repo(tmp_path / "repo", sidecar_dask="2026.11.0", cli_dask="2026.8.0")
    (repo / SIDECAR_LOCKFILE).write_text("cloudpickle==3.1.2\n")

    result = _run_sync(sync_script, repo, "dask==2026.11.0\n", fake_uv_env)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _uv_calls(fake_uv_env) == []
    assert "no dask pin" in result.stdout
