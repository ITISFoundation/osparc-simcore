# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import pytest
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.application import BaseApplicationSettings


@pytest.fixture
def envs_from_docker_inspect() -> EnvVarsDict:
    #  docker image inspect local/storage:development | jq ".[0].Config.Env"
    envs = [
        "PATH=/home/scu/.venv/bin:/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG=C.UTF-8",
        "GPG_KEY=A035C8C19219BA821ECEA86B64E628F8D684696D",
        "PYTHON_VERSION=3.11.9",
        "PYTHON_PIP_VERSION=22.3.1",
        "PYTHON_SETUPTOOLS_VERSION=65.5.1",
        "PYTHON_GET_PIP_URL=https://github.com/pypa/get-pip/raw/d5cb0afaf23b8520f1bbcfed521017b4a95f5c01/public/get-pip.py",
        "PYTHON_GET_PIP_SHA256=394be00f13fa1b9aaa47e911bdb59a09c3b2986472130f30aa0bfaf7f3980637",
        "SC_USER_ID=8004",
        "SC_USER_NAME=scu",
        "SC_BUILD_TARGET=development",
        "SC_BOOT_MODE=default",
        "PYTHONDONTWRITEBYTECODE=1",
        "VIRTUAL_ENV=/home/scu/.venv",
        "SC_DEVEL_MOUNT=/devel/services/storage/",
    ]
    return EnvVarsDict(env.split("=") for env in envs)


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch, envs_from_docker_inspect: EnvVarsDict
) -> EnvVarsDict:
    return setenvs_from_dict(monkeypatch, envs_from_docker_inspect)


def test_applicaton_settings(app_environment: EnvVarsDict):

    # should not raise
    settings = BaseApplicationSettings.create_from_envs()

    # some check
    assert int(app_environment["SC_USER_ID"]) == settings.SC_USER_ID
