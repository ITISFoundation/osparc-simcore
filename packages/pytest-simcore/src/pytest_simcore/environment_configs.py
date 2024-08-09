# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import re
from pathlib import Path
from typing import Any

import pytest

from .helpers.monkeypatch_envs import load_dotenv, setenvs_from_dict
from .helpers.typing_env import EnvVarsDict


def pytest_addoption(parser: pytest.Parser):
    simcore_group = parser.getgroup("simcore")
    simcore_group.addoption(
        "--external-envfile",
        action="store",
        type=Path,
        default=None,
        help="Path to an env file. Consider passing a link to repo configs, i.e. `ln -s /path/to/osparc-ops-config/repo.config`",
    )


@pytest.fixture(scope="session")
def external_envfile_dict(request: pytest.FixtureRequest) -> EnvVarsDict:
    """
    If a file under test folder prefixed with `.env-secret` is present,
    then this fixture captures it.

    This technique allows reusing the same tests to check against
    external development/production servers
    """
    envs = {}
    if envfile := request.config.getoption("--external-envfile"):
        print("🚨 EXTERNAL `envfile` option detected. Loading", envfile, "...")

        assert isinstance(envfile, Path)
        assert envfile.is_file()

        envs = load_dotenv(envfile)

    return envs


@pytest.fixture(scope="session")
def skip_if_external_envfile_dict(external_envfile_dict: EnvVarsDict) -> None:
    if not external_envfile_dict:
        pytest.skip(reason="Skipping test since external-envfile is not set")


@pytest.fixture(scope="session")
def env_devel_dict(env_devel_file: Path) -> EnvVarsDict:
    assert env_devel_file.exists()
    assert env_devel_file.name == ".env-devel"
    return load_dotenv(env_devel_file, verbose=True, interpolate=True)


@pytest.fixture
def mock_env_devel_environment(
    env_devel_dict: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    return setenvs_from_dict(monkeypatch, {**env_devel_dict})


#
# ENVIRONMENT IN A SERVICE
#


@pytest.fixture(scope="session")
def service_name(project_slug_dir: Path) -> str:
    """
    project_slug_dir MUST be defined on root's conftest.py
    """
    return project_slug_dir.name


@pytest.fixture(scope="session")
def services_docker_compose_dict(services_docker_compose_file: Path) -> EnvVarsDict:
    # NOTE: By keeping import here, this library is ONLY required when the fixture is used
    import yaml

    content = yaml.safe_load(services_docker_compose_file.read_text())
    assert "services" in content
    return content


@pytest.fixture
def docker_compose_service_environment_dict(
    services_docker_compose_dict: dict[str, Any],
    env_devel_dict: EnvVarsDict,
    service_name: str,
    env_devel_file: Path,
) -> EnvVarsDict:
    """Returns env vars dict from the docker-compose `environment` section

    - env_devel_dict in environment_configs plugin
    - service_name needs to be defined
    """
    service = services_docker_compose_dict["services"][service_name]

    def _substitute(key, value):
        if m := re.match(r"\${([^{}:-]\w+)", value):
            expected_env_var = m.group(1)
            try:
                # NOTE: if this raises, then the RHS env-vars in the docker-compose are
                # not defined in the env-devel
                if value := env_devel_dict[expected_env_var]:
                    return key, value
            except KeyError:
                pytest.fail(
                    f"{expected_env_var} is not defined in {env_devel_file} but used in docker-compose services[{service}].environment[{key}]"
                )
        return None

    envs: EnvVarsDict = {}
    for key, value in service.get("environment", {}).items():
        if found := _substitute(key, value):
            _, new_value = found
            envs[key] = new_value

    return envs
