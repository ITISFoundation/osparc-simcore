# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-name-in-module

import json
import os

import pytest
from aiohttp import web
from models_library.utils.json_serialization import json_dumps
from pydantic import HttpUrl, parse_obj_as
from pytest_simcore.helpers.monkeypatch_envs import (
    setenvs_from_dict,
    setenvs_from_envfile,
)
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_webserver.application_settings import (
    APP_SETTINGS_KEY,
    ApplicationSettings,
    setup_settings,
)


@pytest.fixture
def mock_env_devel_environment(
    mock_env_devel_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    # Overrides to ensure dev-features are enabled testings
    return mock_env_devel_environment | setenvs_from_dict(
        monkeypatch,
        envs={
            "WEBSERVER_DEV_FEATURES_ENABLED": "1",
        },
    )


@pytest.fixture
def mock_env_makefile(monkeypatch: pytest.MonkeyPatch) -> EnvVarsDict:
    """envvars produced @Makefile (export)"""
    # TODO: add Makefile recipe 'make dump-envs' to produce the file we load here
    return setenvs_from_dict(
        monkeypatch,
        {
            "API_SERVER_API_VERSION": "0.3.0",
            "BUILD_DATE": "2022-01-14T21:28:15Z",
            "CATALOG_API_VERSION": "0.3.2",
            "CLIENT_WEB_OUTPUT": "/home/crespo/devp/osparc-simcore/services/static-webserver/client/source-output",
            "DATCORE_ADAPTER_API_VERSION": "0.1.0-alpha",
            "DIRECTOR_API_VERSION": "0.1.0",
            "DIRECTOR_V2_API_VERSION": "2.0.0",
            "DOCKER_IMAGE_TAG": "production",
            "DOCKER_REGISTRY": "local",
            "S3_ENDPOINT": "http://127.0.0.1:9001",
            "STORAGE_API_VERSION": "0.2.1",
            "SWARM_HOSTS": "",
            "SWARM_STACK_NAME": "master-simcore",
            "SWARM_STACK_NAME_NO_HYPHEN": "master_simcore",
            "VCS_REF_CLIENT": "99b8022d2",
            "VCS_STATUS_CLIENT": "'modified/untracked'",
            "VCS_URL": "git@github.com:pcrespov/osparc-simcore.git",
            "WEBSERVER_API_VERSION": "0.7.0",
        },
    )


@pytest.fixture
def mock_env_dockerfile_build(monkeypatch: pytest.MonkeyPatch) -> EnvVarsDict:
    #
    # docker run -it --hostname "{{.Node.Hostname}}-{{.Service.Name}}-{{.Task.Slot}}" local/webserver:production printenv
    #
    return setenvs_from_envfile(
        monkeypatch,
        """\
        GPG_KEY=123456789123456789
        HOME=/home/scu
        HOSTNAME=osparc-master-55-master-simcore_master_webserver-1
        IS_CONTAINER_CONTEXT=Yes
        LANG=C.UTF-8
        PATH=/home/scu/.venv/bin:/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
        PWD=/home/scu
        PYTHON_GET_PIP_SHA256=6123659241292b2147b58922b9ffe11dda66b39d52d8a6f3aa310bc1d60ea6f7
        PYTHON_GET_PIP_URL=https://github.com/pypa/get-pip/raw/a1675ab6c2bd898ed82b1f58c486097f763c74a9/public/get-pip.py
        PYTHON_PIP_VERSION=21.1.3
        PYTHON_VERSION=3.11.9
        PYTHONDONTWRITEBYTECODE=1
        PYTHONOPTIMIZE=TRUE
        SC_BOOT_MODE=production
        SC_BUILD_DATE=2022-01-09T12:26:29Z
        SC_BUILD_TARGET=production
        SC_HEALTHCHECK_INTERVAL=30
        SC_HEALTHCHECK_RETRY=3
        SC_USER_ID=8004
        SC_USER_NAME=scu
        SC_VCS_REF=dd536f998
        SC_VCS_URL=git@github.com:ITISFoundation/osparc-simcore.git
        TERM=xterm
        VIRTUAL_ENV=/home/scu/.venv
    """,
    )


@pytest.fixture
def mock_webserver_service_environment(
    monkeypatch: pytest.MonkeyPatch,
    mock_env_makefile: EnvVarsDict,
    mock_env_devel_environment: EnvVarsDict,
    mock_env_dockerfile_build: EnvVarsDict,
    mock_env_deployer_pipeline: EnvVarsDict,
) -> EnvVarsDict:
    """
    Mocks environment produce in the docker compose config with a .env (.env-devel)
    and launched with a makefile
    """
    # @docker compose config (overrides)
    # TODO: get from docker compose config
    # r'- ([A-Z2_]+)=\$\{\1:-([\w-]+)\}'

    # - .env-devel + docker-compose service environs
    #     hostname: "{{.Node.Hostname}}-{{.Service.Name}}-{{.Task.Slot}}"

    #     environment:
    #         - CATALOG_HOST=${CATALOG_HOST:-catalog}
    #         - CATALOG_PORT=${CATALOG_PORT:-8000}
    #         - DIAGNOSTICS_MAX_AVG_LATENCY=10
    #         - DIAGNOSTICS_MAX_TASK_DELAY=30
    #         - DIRECTOR_PORT=${DIRECTOR_PORT:-8080}
    #         - DIRECTOR_V2_HOST=${DIRECTOR_V2_HOST:-director-v2}
    #         - DIRECTOR_V2_PORT=${DIRECTOR_V2_PORT:-8000}
    #         - STORAGE_HOST=${STORAGE_HOST:-storage}
    #         - STORAGE_PORT=${STORAGE_PORT:-8080}
    #         - SWARM_STACK_NAME=${SWARM_STACK_NAME:-simcore}
    #         - WEBSERVER_LOGLEVEL=${LOG_LEVEL:-WARNING}
    #     env_file:
    #         - ../.env
    mock_envs_docker_compose_environment = setenvs_from_dict(
        monkeypatch,
        {
            # Emulates MYVAR=${MYVAR:-default}
            "CATALOG_HOST": os.environ.get("CATALOG_HOST", "catalog"),
            "CATALOG_PORT": os.environ.get("CATALOG_PORT", "8000"),
            "DIAGNOSTICS_MAX_AVG_LATENCY": "30",
            "DIRECTOR_PORT": os.environ.get("DIRECTOR_PORT", "8080"),
            "DIRECTOR_V2_HOST": os.environ.get("DIRECTOR_V2_HOST", "director-v2"),
            "DIRECTOR_V2_PORT": os.environ.get("DIRECTOR_V2_PORT", "8000"),
            "STORAGE_HOST": os.environ.get("STORAGE_HOST", "storage"),
            "STORAGE_PORT": os.environ.get("STORAGE_PORT", "8080"),
            "SWARM_STACK_NAME": os.environ.get("SWARM_STACK_NAME", "simcore"),
            "WEBSERVER_LOGLEVEL": os.environ.get("LOG_LEVEL", "WARNING"),
            "SESSION_COOKIE_MAX_AGE": str(7 * 24 * 60 * 60),
        },
    )

    return (
        mock_env_makefile
        | mock_env_devel_environment
        | mock_env_dockerfile_build
        | mock_env_deployer_pipeline
        | mock_envs_docker_compose_environment
    )


@pytest.fixture
def app_settings(
    mock_webserver_service_environment: EnvVarsDict,
) -> ApplicationSettings:
    app = web.Application()

    # init and validation happens here
    settings = setup_settings(app)
    print("envs\n", json.dumps(mock_webserver_service_environment, indent=1))
    print("settings:\n", settings.json(indent=1))

    assert APP_SETTINGS_KEY in app
    assert app[APP_SETTINGS_KEY] == settings
    return settings


def test_settings_constructs(app_settings: ApplicationSettings):
    assert "vcs_url" in app_settings.public_dict()
    assert (
        app_settings.public_dict()["vcs_url"]
        == "git@github.com:ITISFoundation/osparc-simcore.git"
    )

    assert "app_name" in app_settings.public_dict()
    assert "api_version" in app_settings.public_dict()

    # assert can jsonify w/o raising
    print("public_dict:", json_dumps(app_settings.public_dict(), indent=1))


def test_settings_to_client_statics(app_settings: ApplicationSettings):
    statics = app_settings.to_client_statics()

    # assert can jsonify w/o raising
    print("statics:", json_dumps(statics, indent=1))

    # all key in camelcase
    assert all(
        key[0] == key[0].lower() and "_" not in key and key.lower() != key
        for key in statics
    ), f"Got {list(statics.keys())}"

    # special alias
    assert statics["stackName"] == "master-simcore"
    assert statics["pluginsDisabled"] == ["WEBSERVER_CLUSTERS"]


def test_settings_to_client_statics_plugins(
    mock_webserver_service_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
):
    disable_plugins = {"WEBSERVER_EXPORTER", "WEBSERVER_SCICRUNCH"}
    for name in disable_plugins:
        monkeypatch.setenv(name, "null")

    monkeypatch.setenv("WEBSERVER_VERSION_CONTROL", "0")
    disable_plugins.add("WEBSERVER_VERSION_CONTROL")

    monkeypatch.setenv("WEBSERVER_FOLDERS", "0")
    disable_plugins.add("WEBSERVER_FOLDERS")

    settings = ApplicationSettings.create_from_envs()
    statics = settings.to_client_statics()

    print("STATICS:\n", json_dumps(statics, indent=1))

    assert settings.WEBSERVER_LOGIN

    assert (
        statics["webserverLogin"]["LOGIN_ACCOUNT_DELETION_RETENTION_DAYS"]
        == settings.WEBSERVER_LOGIN.LOGIN_ACCOUNT_DELETION_RETENTION_DAYS
    )
    assert (
        statics["webserverLogin"]["LOGIN_2FA_REQUIRED"]
        == settings.WEBSERVER_LOGIN.LOGIN_2FA_REQUIRED
    )
    assert (
        statics["webserverSession"].get("SESSION_COOKIE_MAX_AGE")
        == settings.WEBSERVER_SESSION.SESSION_COOKIE_MAX_AGE
    )

    assert statics["vcsReleaseTag"]
    assert parse_obj_as(HttpUrl, statics["vcsReleaseUrl"])

    assert set(statics["pluginsDisabled"]) == (disable_plugins | {"WEBSERVER_CLUSTERS"})


def test_avoid_sensitive_info_in_public(app_settings: ApplicationSettings):
    # avoids display of sensitive info
    assert not any("pass" in key for key in app_settings.public_dict())
    assert not any("token" in key for key in app_settings.public_dict())
    assert not any("secret" in key for key in app_settings.public_dict())
    assert not any("private" in key for key in app_settings.public_dict())
