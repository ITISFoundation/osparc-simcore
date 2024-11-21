# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import json
import os
import shutil
import subprocess
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import pytest
import yaml
from common_library.json_serialization import json_loads
from service_integration import cli
from typer.testing import CliRunner, Result


def _git_version() -> str:
    return subprocess.run(
        ["git", "--version"],
        capture_output=True,
        encoding="utf8",
        check=True,
    ).stdout.strip()


def _download_git_commit(repository: str, commit_sha: str, directory: Path):
    subprocess.run(
        [
            "git",
            "clone",
            "--verbose",
            "--progress",
            "--shallow-since=2022-08-01",
            repository,
            f"{directory}",
        ],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "checkout",
            commit_sha,
        ],
        check=True,
        cwd=directory,
    )
    return directory


@pytest.fixture(scope="module")
def jupytermath_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    print("Running git", _git_version())
    tmp_path = tmp_path_factory.mktemp("jupytermath_repo")
    repo_dir = _download_git_commit(
        repository="https://github.com/ITISFoundation/jupyter-math",
        commit_sha="ad51f531548e88afa3ffe3b702a89d159ad8be7f",
        directory=tmp_path / "jupyter-math",
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
                "simcore-service-integrator",
                " ".join(cmd),
                f"at {workdir=}",
            )
            print("ENV:", runner.make_env())
            #
            result = runner.invoke(cli.app, list(cmd))
            return Path(workdir), result

        yield _invoke


@pytest.fixture
def compose_spec_reference(tests_data_dir: Path) -> dict[str, Any]:
    """This file was created as

    $ git clone https://github.com/ITISFoundation/jupyter-math
    $ git checkout ad51f531548e88afa3ffe3b702a89d159ad8be7f
    $ make compose-spec
    Unable to find image 'itisfoundation/ci-service-integration-library:v1.0.1-dev-25' locally
    v1.0.1-dev-25: Pulling from itisfoundation/ci-service-integration-library
    284055322776: Pull complete
    add8cbaa9fce: Pull complete
    a884b5401cbf: Pull complete
    dafa3e5bf39d: Pull complete
    be7367c7df12: Pull complete
    9437169e9a8d: Pull complete
    fe201c3ac6ff: Pull complete
    d4c4d0b4fa1a: Pull complete
    9cfd37a6308f: Pull complete
    f8f83b7570ef: Pull complete
    7824be4287c4: Pull complete
    3726662bd420: Pull complete
    4f4fb700ef54: Pull complete
    bfc854eefa69: Pull complete
    f7a90cb7e788: Pull complete
    aa18a9f23db5: Pull complete
    6b69e2d61e06: Pull complete
    f6e038784f3d: Pull complete
    0840c17d89ee: Pull complete
    Digest: sha256:279a297b49f1fddb26289d205d4ba5acca1bb8e7bedadcfce00f821873935c03
    Status: Downloaded newer image for itisfoundation/ci-service-integration-library:v1.0.1-dev-25
    """
    return yaml.safe_load(
        (tests_data_dir / "docker-compose_jupyter-math_ad51f53.yml").read_text()
    )


def test_ooil_compose_wo_arguments(
    run_program_in_repo: Callable[..., tuple[Path, Result]],
    compose_spec_reference: dict[str, Any],
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

    # Comparison compose-specs
    #  following up with https://github.com/ITISFoundation/osparc-simcore/pull/3433#issuecomment-1275728062
    #
    # PR 2657 does not seem to correspond to the version in the image 'itisfoundation/ci-service-integration-library:v1.0.1-dev-25'!
    # https://github.com/ITISFoundation/osparc-simcore/pull/2657/files#diff-908bfee2900285b2cfe9ec71fae205aa0527c840a293f5b3497e1a9157c65c65L39
    #
    assert compose_spec_reference["services"]["jupyter-math"]["build"].pop("args") == {
        "VERSION": "2.0.8"
    }

    # new ooil has complete SHA
    compose_spec_reference["services"]["jupyter-math"]["build"]["labels"][
        "org.label-schema.vcs-ref"
    ] = "ad51f531548e88afa3ffe3b702a89d159ad8be7f"

    # different dates
    compose_spec["services"]["jupyter-math"]["build"]["labels"][
        "org.label-schema.build-date"
    ] = compose_spec_reference["services"]["jupyter-math"]["build"]["labels"][
        "org.label-schema.build-date"
    ]

    label_keys = compose_spec_reference["services"]["jupyter-math"]["build"][
        "labels"
    ].keys()

    # NOTE: generally it is not a good idea to compare serialized values. It is difficult to debug
    # when it fails and a failure is not always indicative of a real error e.g. orjson serializes diffferently
    # to json.
    for k in label_keys:

        got_label_value = compose_spec["services"]["jupyter-math"]["build"]["labels"][k]
        expected_label_value = compose_spec_reference["services"]["jupyter-math"][
            "build"
        ]["labels"][k]
        if k.startswith("io.simcore"):
            assert json_loads(got_label_value) == json_loads(expected_label_value)
        assert (
            got_label_value == expected_label_value
        ), f"label {k} got a different dump"

    assert compose_spec == compose_spec_reference
