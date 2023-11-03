# pylint:disable=redefined-outer-name

import re
from pathlib import Path

import pytest
import simcore_service_dynamic_scheduler
import yaml
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict

pytest_plugins = [
    "pytest_simcore.cli_runner",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.repository_paths",
]


@pytest.fixture(scope="session")
def project_slug_dir(osparc_simcore_root_dir: Path) -> Path:
    # fixtures in pytest_simcore.environs
    service_folder = osparc_simcore_root_dir / "services" / "dynamic-scheduler"
    assert service_folder.exists()
    assert any(service_folder.glob("src/simcore_service_dynamic_scheduler"))
    return service_folder


@pytest.fixture(scope="session")
def installed_package_dir() -> Path:
    dirpath = Path(simcore_service_dynamic_scheduler.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture
def docker_compose_service_dynamic_scheduler_env_vars(
    services_docker_compose_file: Path,
    env_devel_dict: EnvVarsDict,
) -> EnvVarsDict:
    """env vars injected at the docker-compose"""

    dynamic_scheduler = yaml.safe_load(services_docker_compose_file.read_text())[
        "services"
    ]["dynamic-scheduler"]

    def _substitute(item):
        key, value = item.split("=")
        if m := re.match(r"\${([^{}:-]\w+)", value):
            expected_env_var = m.group(1)
            try:
                # NOTE: if this raises, then the RHS env-vars in the docker-compose are
                # not defined in the env-devel
                if value := env_devel_dict[expected_env_var]:
                    return key, value
            except KeyError:
                pytest.fail(
                    f"{expected_env_var} is not defined in .env-devel but used in docker-compose"
                    f" services[{dynamic_scheduler}].environment[{key}]"
                )
        return None

    envs: EnvVarsDict = {}
    for item in dynamic_scheduler.get("environment", []):
        if found := _substitute(item):
            key, value = found
            envs[key] = value

    return envs


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    docker_compose_service_dynamic_scheduler_env_vars: EnvVarsDict,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {**docker_compose_service_dynamic_scheduler_env_vars},
    )
