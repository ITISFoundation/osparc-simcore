# pylint: disable=redefined-outer-name

import re
from pathlib import Path

import pytest
import yaml
from pytest_simcore.helpers.docker import (
    filter_compose_file_for_ci,
    filter_service_names_for_ci,
)

_CI_ALLOWED = ("postgres", "redis")


@pytest.fixture
def compose_file(tmp_path: Path) -> Path:
    compose_path = tmp_path / "docker-compose.yml"
    compose_path.write_text(
        yaml.safe_dump(
            {
                "services": {
                    "postgres": {"image": "postgres"},
                    "adminer": {"image": "adminer", "depends_on": ["postgres"]},
                    "redis": {"image": "redis"},
                }
            }
        )
    )
    return compose_path


@pytest.fixture
def in_ci(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> bool:
    if request.param:
        monkeypatch.setenv("CI", "true")
    else:
        monkeypatch.delenv("CI", raising=False)
    return request.param


@pytest.mark.parametrize("in_ci", [False], indirect=True)
def test_filter_service_names_keeps_all_outside_ci(in_ci: bool):
    assert filter_service_names_for_ci(["adminer", "postgres"], _CI_ALLOWED) == ["adminer", "postgres"]


@pytest.mark.parametrize("in_ci", [True], indirect=True)
def test_filter_service_names_keeps_only_allowed_in_ci(in_ci: bool):
    assert filter_service_names_for_ci(["adminer", "postgres"], _CI_ALLOWED) == ["postgres"]


@pytest.mark.parametrize("in_ci", [True], indirect=True)
def test_filter_service_names_can_end_up_empty_in_ci(in_ci: bool):
    assert filter_service_names_for_ci(["adminer"], _CI_ALLOWED) == []


@pytest.mark.parametrize("in_ci", [False], indirect=True)
def test_filter_compose_file_returns_original_outside_ci(in_ci: bool, compose_file: Path, tmp_path: Path):
    assert filter_compose_file_for_ci(compose_file, _CI_ALLOWED, tmp_path) == compose_file


@pytest.mark.parametrize("in_ci", [True], indirect=True)
def test_filter_compose_file_drops_not_allowed_in_ci(in_ci: bool, compose_file: Path, tmp_path: Path):
    destination_dir = tmp_path / "filtered"
    destination_dir.mkdir()

    filtered_path = filter_compose_file_for_ci(compose_file, _CI_ALLOWED, destination_dir)

    assert filtered_path != compose_file
    assert sorted(yaml.safe_load(filtered_path.read_text())["services"]) == ["postgres", "redis"]
    # the original is left untouched so that it can still be used locally
    assert "adminer" in yaml.safe_load(compose_file.read_text())["services"]


@pytest.mark.parametrize("in_ci", [True], indirect=True)
def test_filter_compose_file_returns_original_when_all_allowed(in_ci: bool, compose_file: Path, tmp_path: Path):
    assert filter_compose_file_for_ci(compose_file, ("adminer", "postgres", "redis"), tmp_path) == compose_file


_DOCKER_COMPOSE_FILE_FIXTURE_RE = re.compile(r"^def docker_compose_file\(", re.MULTILINE)
_SKIPPED_DIRS = (".git", ".venv", "node_modules")


def test_every_docker_compose_file_fixture_filters_for_ci(osparc_simcore_root_dir: Path):
    """Guards against re-introducing yet another way of keeping debug-only containers out of the CI

    Every override of the pytest-docker 'docker_compose_file' fixture must go through
    'filter_compose_file_for_ci', otherwise its compose file starts every service it declares in the CI.
    """
    offenders = [
        conftest_path.relative_to(osparc_simcore_root_dir)
        for conftest_path in osparc_simcore_root_dir.rglob("conftest.py")
        if not any(part in _SKIPPED_DIRS for part in conftest_path.parts)
        and _DOCKER_COMPOSE_FILE_FIXTURE_RE.search(content := conftest_path.read_text())
        and "filter_compose_file_for_ci" not in content
    ]

    assert not offenders, (
        f"{offenders} override the 'docker_compose_file' fixture without filtering it for the CI."
        " Use 'pytest_simcore.helpers.docker.filter_compose_file_for_ci'"
    )
