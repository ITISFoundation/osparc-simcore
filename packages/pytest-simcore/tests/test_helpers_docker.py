# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import re
from pathlib import Path

import docker
import pytest
import pytest_simcore
import yaml
from pytest_simcore.helpers.docker import (
    _get_service_published_port,
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
_SKIPPED_DIRS = (".git", ".venv", "node_modules", ".cache")


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


_PUBLISHED_PORT_CALL_RE = re.compile(r"get_service_published_port\(\s*['\"]([^'\"]+)['\"]")


def test_published_port_lookups_name_real_compose_services(osparc_simcore_root_dir: Path):
    """lookups must not depend on the stack name they are deployed under

    swarm deploys each service as "{stack}_{service}" and the lookup keeps candidates whose name
    *ends with* the requested name. e.g. "simcore_redis" only ever matched because the stack was
    named "pytest-simcore" ("pytest-simcore_redis"); run-scoped stack names remove that
    coincidence, so every literal lookup name must be an actual compose service key.

    f-string call sites build the full "{stack}_{service}" name and are validated at runtime
    against the deployed compose, so they are not scanned here.
    """
    lookup_names = {
        name
        for module in (Path(pytest_simcore.__file__).parent).rglob("*.py")
        for name in _PUBLISHED_PORT_CALL_RE.findall(module.read_text())
    }
    assert lookup_names, "the scan found no lookup literals: the regex needs updating"

    compose_service_keys = {
        service_key
        for compose_filename in ("docker-compose.yml", "docker-compose-ops.yml")
        for service_key in yaml.safe_load((osparc_simcore_root_dir / "services" / compose_filename).read_text())[
            "services"
        ]
    }

    unknown = lookup_names - compose_service_keys
    assert not unknown, f"{sorted(unknown)} are not services in services/docker-compose*.yml"


class _FakeService:
    def __init__(self, name: str, ports: list[dict] | None = None) -> None:
        self.name = name
        self.attrs = {"Endpoint": {"Ports": ports if ports is not None else []}}


class _FakeServices:
    def __init__(self, services: list[_FakeService]) -> None:
        self._services = services

    def list(self) -> list[_FakeService]:
        return self._services


class _FakeClient:
    def __init__(self, services: list[_FakeService]) -> None:
        self.services = _FakeServices(services)


@pytest.fixture
def fake_docker(monkeypatch: pytest.MonkeyPatch):
    def _install(services: list[_FakeService]):
        monkeypatch.setattr(docker, "from_env", lambda: _FakeClient(services))

    return _install


def test_published_port_lookup_error_reports_the_stack_filter(fake_docker) -> None:
    # another checkout's service exists but is filtered out: the error must say what was
    # looked for and what IS on the daemon, so a wrong stack_name is diagnosable
    fake_docker([_FakeService("pytest-other-ops-1234_postgres")])
    with pytest.raises(RuntimeError) as excinfo:
        _get_service_published_port("postgres", None, stack_name="pytest-this-core-abcd")
    message = f"{excinfo.value}"
    assert "pytest-this-core-abcd_postgres" in message
    assert "pytest-other-ops-1234_postgres" in message


def test_published_port_lookup_error_names_the_resolved_service(fake_docker) -> None:
    fake_docker([_FakeService("pytest-this-core-abcd_postgres", ports=[])])
    with pytest.raises(RuntimeError) as excinfo:
        _get_service_published_port("postgres", None, stack_name="pytest-this-core-abcd")
    assert "pytest-this-core-abcd_postgres" in f"{excinfo.value}"
