# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Iterable

import pytest
import yaml
from pytest import TempPathFactory
from service_integration import cli
from typer.testing import CliRunner, Result


def _git_version() -> str:
    return subprocess.run(
        ["git", "--version"],
        capture_output=True,
        encoding="utf8",
        check=True,
    ).stdout.strip()


def _git_shallow_clone(repository: str, directory: Path):
    subprocess.run(
        [
            "git",
            "clone",
            "--depth=1",
            "--verbose",
            "--progress",
            repository,
            f"{directory}",
        ],
        check=True,
    )
    return directory


@pytest.fixture(scope="module")
def jupytermath_repo(tmp_path_factory: TempPathFactory) -> Path:
    print("Running git", _git_version())
    tmp_path = tmp_path_factory.mktemp("jupytermath_repo")
    repo_dir = _git_shallow_clone(
        "https://github.com/ITISFoundation/jupyter-math", tmp_path / "jupyter-math"
    )
    assert repo_dir.exists()
    os.system(f"ls -la {repo_dir}")
    return repo_dir


@pytest.fixture
def run_program_in_repo(tmp_path: Path, jupytermath_repo: Path) -> Iterable[Callable]:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as workdir:
        shutil.copytree(jupytermath_repo, workdir, dirs_exist_ok=True)
        os.system(f"ls -la {workdir}")

        def _invoke(*cmd) -> tuple[Path, Result]:
            print(
                "RUNNING",
                "osparc-service-integrator",
                " ".join(cmd),
                f"at {workdir=}",
            )
            print("ENV:", runner.make_env())
            #
            result = runner.invoke(cli.app, list(cmd))
            return Path(workdir), result

        yield _invoke


def test_ooil_compose_wo_arguments(
    run_program_in_repo: Callable[..., tuple[Path, Result]],
):
    # After https://github.com/ITISFoundation/osparc-simcore/pull/3433#pullrequestreview-1138481844
    #
    # this test reproduces the calls with ooil in jupyter-math repo:
    #
    # SEE https://github.com/ITISFoundation/jupyter-math/blob/ad51f531548e88afa3ffe3b702a89d159ad8be7f/Makefile#L29
    # SEE https://github.com/ITISFoundation/jupyter-math/blob/ad51f531548e88afa3ffe3b702a89d159ad8be7f/.github/workflows/check-image.yml#L18
    #

    # NOTE: defaults searches for configs in .osparc/**/metadata.yml
    workdir, result = run_program_in_repo(
        "compose",
    )
    assert result.exit_code == os.EX_OK, result.output

    # should produce compose-specs file
    compose_spec_path = workdir / "docker-compose.yml"
    assert compose_spec_path.exists()

    # some checks compose-specs content
    compose_spec = yaml.safe_load(compose_spec_path.read_text())
    print(json.dumps(compose_spec, indent=1))

    assert "jupyter-math" in compose_spec["services"]

    labels = compose_spec["services"]["jupyter-math"]["build"]["labels"]
    assert (
        labels["org.label-schema.vcs-url"]
        == "https://github.com/ITISFoundation/jupyter-math"
    )
