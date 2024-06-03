# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import re
from pathlib import Path

import pytest
import yaml

from .helpers.typing_env import EnvVarsDict
from .helpers.utils_envs import delenvs_from_dict, load_dotenv, setenvs_from_dict


@pytest.fixture(scope="session")  # MD: get this, I will mock it with my app environmnet
def env_devel_dict(env_devel_file: Path) -> EnvVarsDict:
    assert env_devel_file.exists()
    assert env_devel_file.name == ".env-devel"
    return load_dotenv(env_devel_file, verbose=True, interpolate=True)


@pytest.fixture
def mock_env_devel_environment(
    env_devel_dict: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    return setenvs_from_dict(monkeypatch, env_devel_dict)


@pytest.fixture
def all_env_devel_undefined(
    monkeypatch: pytest.MonkeyPatch, env_devel_dict: EnvVarsDict
):
    """Ensures that all env vars in .env-devel are undefined in the test environment

    NOTE: this is useful to have a clean starting point and avoid
    the environment to influence your test. I found this situation
    when some script was accidentaly injecting the entire .env-devel in the environment
    """
    delenvs_from_dict(monkeypatch, env_devel_dict, raising=False)


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


@pytest.fixture
def docker_compose_service_environment_dict(
    services_docker_compose_file: Path, env_devel_dict: EnvVarsDict, service_name: str
) -> EnvVarsDict:
    """Returns env vars dict from the docker-compose `environment` section

    - services_docker_compose_file in repository_paths plugin
    - env_devel_dict in environment_configs plugin
    - service_name needs to be defined
    """
    service = yaml.safe_load(services_docker_compose_file.read_text())["services"][
        service_name
    ]

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
                    f"{expected_env_var} is not defined in .env-devel but used in docker-compose services[{service}].environment[{key}]"
                )
        return None

    envs: EnvVarsDict = {}
    for key, value in service.get("environment", {}).items():
        if found := _substitute(key, value):
            _, new_value = found
            envs[key] = new_value

    return envs
