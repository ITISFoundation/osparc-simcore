# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-name-in-module

import argparse
import json
import os
import re
from typing import Dict

import pytest
from aiohttp import web
from simcore_service_webserver.application_settings import (
    APP_SETTINGS_KEY,
    ApplicationSettings,
    setup_settings,
)
from simcore_service_webserver.cli import parse, setup_parser

# FIXTURES -----------------------------


@pytest.fixture
def mock_env_makefile(monkeypatch):
    """envvars produced @Makefile (export)"""

    # TODO: make dump-envs shall produce a file that we load here
    monkeypatch.setenv("API_SERVER_API_VERSION", "0.3.0")
    monkeypatch.setenv("BUILD_DATE", "2022-01-14T21:28:15Z")
    monkeypatch.setenv("CATALOG_API_VERSION", "0.3.2")
    monkeypatch.setenv(
        "CLIENT_WEB_OUTPUT",
        "/home/crespo/devp/osparc-simcore/services/web/client/source-output",
    )
    monkeypatch.setenv("DATCORE_ADAPTER_API_VERSION", "0.1.0-alpha")
    monkeypatch.setenv("DIRECTOR_API_VERSION", "0.1.0")
    monkeypatch.setenv("DIRECTOR_V2_API_VERSION", "2.0.0")
    monkeypatch.setenv("DOCKER_IMAGE_TAG", "production")
    monkeypatch.setenv("DOCKER_REGISTRY", "local")
    monkeypatch.setenv("S3_ENDPOINT", "127.0.0.1:9001")
    monkeypatch.setenv("STORAGE_API_VERSION", "0.2.1")
    monkeypatch.setenv("SWARM_HOSTS", "")
    monkeypatch.setenv("SWARM_STACK_NAME", "master-simcore")
    monkeypatch.setenv("SWARM_STACK_NAME_NO_HYPHEN", "master_simcore")
    monkeypatch.setenv("VCS_REF_CLIENT", "99b8022d2")
    monkeypatch.setenv("VCS_STATUS_CLIENT", "'modified/untracked'")
    monkeypatch.setenv("VCS_URL", "git@github.com:pcrespov/osparc-simcore.git")
    monkeypatch.setenv("WEBSERVER_API_VERSION", "0.7.0")


@pytest.fixture
def mock_env_Dockerfile_build(monkeypatch):
    # docker run -it --hostname "{{.Node.Hostname}}-{{.Service.Name}}-{{.Task.Slot}}" local/webserver:production printenv
    PRINTENV_OUTPUT = """
        GPG_KEY=123456789123456789
        HOME=/home/scu
        HOSTNAME=osparc-master-02-master-simcore_master_webserver-1
        IS_CONTAINER_CONTEXT=Yes
        LANG=C.UTF-8
        PATH=/home/scu/.venv/bin:/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
        PWD=/home/scu
        PYTHON_GET_PIP_SHA256=6123659241292b2147b58922b9ffe11dda66b39d52d8a6f3aa310bc1d60ea6f7
        PYTHON_GET_PIP_URL=https://github.com/pypa/get-pip/raw/a1675ab6c2bd898ed82b1f58c486097f763c74a9/public/get-pip.py
        PYTHON_PIP_VERSION=21.1.3
        PYTHON_VERSION=3.8.10
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
    """

    for key, value in re.findall(r"(\w+)=(.+)", PRINTENV_OUTPUT):
        monkeypatch.setenv(key, value)


@pytest.fixture
def mock_webserver_service_environment(
    mock_env_makefile,
    mock_env_devel_environment,
    mock_env_Dockerfile_build,
    monkeypatch,
) -> None:
    """
    Mocks environment produce in the docker-compose config with a .env (.env-devel) and launched with a makefile
    """

    def monkeypatch_setenv_default(name, default):
        """Assumes MYVAR=${MYVAR:-default}"""
        if name not in os.environ:
            monkeypatch.setenv(name, default)

    # @docker-compose config (overrides)

    # TODO: get from docker-compose config
    # r'- ([A-Z2_]+)=\$\{\1:-([\w-]+)\}'

    # - .env-devel + docker-compose service environs
    #     hostname: "{{.Node.Hostname}}-{{.Service.Name}}-{{.Task.Slot}}"

    #     environment:
    #         - CATALOG_HOST=${CATALOG_HOST:-catalog}
    #         - CATALOG_PORT=${CATALOG_PORT:-8000}
    #         - DIAGNOSTICS_MAX_AVG_LATENCY=10
    #         - DIAGNOSTICS_MAX_TASK_DELAY=30
    #         - DIRECTOR_HOST=${DIRECTOR_HOST:-director}
    #         - DIRECTOR_PORT=${DIRECTOR_PORT:-8080}
    #         - DIRECTOR_V2_HOST=${DIRECTOR_V2_HOST:-director-v2}
    #         - DIRECTOR_V2_PORT=${DIRECTOR_V2_PORT:-8000}
    #         - STORAGE_HOST=${STORAGE_HOST:-storage}
    #         - STORAGE_PORT=${STORAGE_PORT:-8080}
    #         - SWARM_STACK_NAME=${SWARM_STACK_NAME:-simcore}
    #         - WEBSERVER_LOGLEVEL=${LOG_LEVEL:-WARNING}
    #     env_file:
    #         - ../.env

    monkeypatch_setenv_default("CATALOG_HOST", "catalog")
    monkeypatch_setenv_default("CATALOG_PORT", "8000")
    monkeypatch.setenv("DIAGNOSTICS_MAX_AVG_LATENCY", 30)
    monkeypatch_setenv_default("DIRECTOR_HOST", "director")
    monkeypatch_setenv_default("DIRECTOR_PORT", "8080")
    monkeypatch_setenv_default("DIRECTOR_V2_HOST", "director-v2")
    monkeypatch_setenv_default("DIRECTOR_V2_PORT", "8000")
    monkeypatch_setenv_default("STORAGE_HOST", "storage")
    monkeypatch_setenv_default("STORAGE_PORT", "8080")
    monkeypatch_setenv_default("SWARM_STACK_NAME", "simcore")
    monkeypatch.setenv("WEBSERVER_LOGLEVEL", os.environ.get("LOG_LEVEL", "WARNING"))


@pytest.fixture
def app_settings(mock_webserver_service_environment) -> ApplicationSettings:

    app = web.Application()

    # init and validation happens here
    settings = setup_settings(app)
    print("app settings:\n", settings.json(indent=1))

    assert APP_SETTINGS_KEY in app
    assert app[APP_SETTINGS_KEY] == settings
    return settings


@pytest.fixture(
    params=[
        "server-docker-prod.yaml",
    ]
)
def app_config(request, mock_webserver_service_environment) -> Dict:
    parser = setup_parser(argparse.ArgumentParser("test-parser"))
    config = parse(["-c", request.param], parser)
    print("app config [request.param]:\n", json.dumps(config, indent=1))
    return config


# TESTS -----------------------------


def test_app_settings_with_prod_config(
    app_config: Dict, app_settings: ApplicationSettings
):

    assert app_settings.WEBSERVER_EMAIL is not None
    assert app_settings.WEBSERVER_PROMETHEUS is not None
    assert app_settings.WEBSERVER_REDIS is not None
    assert app_settings.WEBSERVER_TRACING is not None
    assert app_settings.WEBSERVER_CATALOG is not None
    assert app_settings.WEBSERVER_DIRECTOR is not None
    assert app_settings.WEBSERVER_STORAGE is not None
    assert app_settings.WEBSERVER_DIRECTOR_V2 is not None
    assert app_settings.WEBSERVER_RESOURCE_MANAGER is not None
    assert app_settings.WEBSERVER_LOGIN is not None

    # This is basically how the fields in ApplicationSettings map the trafaret's config file
    #
    # This test compares the config produced by trafaret against
    # the equilalent fields captured by ApplicationSettings
    #
    # This guarantees that all configuration from the previous
    # version can be recovered with the new settings approach
    #
    # This test has been used to guide the design of new settings
    #
    #
    assert app_config == {
        "version": "1.0",
        "main": {
            "host": "0.0.0.0",
            "port": app_settings.WEBSERVER_PORT,
            "log_level": f"{app_settings.WEBSERVER_LOG_LEVEL}",
            "testing": False,  # TODO: deprecate!
            "studies_access_enabled": 1
            if app_settings.WEBSERVER_STUDIES_ACCESS_ENABLED
            else 0,
        },
        "tracing": {
            "enabled": 1 if app_settings.WEBSERVER_TRACING is not None else 0,
            "zipkin_endpoint": f"{app_settings.WEBSERVER_TRACING.TRACING_ZIPKIN_ENDPOINT}",
        },
        "socketio": {"enabled": True},
        "director": {
            "enabled": app_settings.WEBSERVER_DIRECTOR is not None,
            "host": app_settings.WEBSERVER_DIRECTOR.DIRECTOR_HOST,
            "port": app_settings.WEBSERVER_DIRECTOR.DIRECTOR_PORT,
            "version": app_settings.WEBSERVER_DIRECTOR.DIRECTOR_VTAG,
        },
        "db": {
            "postgres": {
                "database": app_settings.WEBSERVER_POSTGRES.POSTGRES_DB,
                "endpoint": f"{app_settings.WEBSERVER_POSTGRES.POSTGRES_HOST}:{app_settings.WEBSERVER_POSTGRES.POSTGRES_PORT}",
                "host": app_settings.WEBSERVER_POSTGRES.POSTGRES_HOST,
                "maxsize": app_settings.WEBSERVER_POSTGRES.POSTGRES_MAXSIZE,
                "minsize": app_settings.WEBSERVER_POSTGRES.POSTGRES_MINSIZE,
                "password": app_settings.WEBSERVER_POSTGRES.POSTGRES_PASSWORD.get_secret_value(),
                "port": app_settings.WEBSERVER_POSTGRES.POSTGRES_PORT,
                "user": app_settings.WEBSERVER_POSTGRES.POSTGRES_USER,
            },
            "enabled": app_settings.WEBSERVER_POSTGRES is not None,
        },
        "resource_manager": {
            "enabled": (
                app_settings.WEBSERVER_REDIS is not None
                and app_settings.WEBSERVER_RESOURCE_MANAGER is not None
            ),
            "resource_deletion_timeout_seconds": app_settings.WEBSERVER_RESOURCE_MANAGER.RESOURCE_MANAGER_RESOURCE_TTL_S,
            "garbage_collection_interval_seconds": app_settings.WEBSERVER_RESOURCE_MANAGER.RESOURCE_MANAGER_GARBAGE_COLLECTION_INTERVAL_S,
            "redis": {
                "enabled": app_settings.WEBSERVER_REDIS is not None,
                "host": app_settings.WEBSERVER_REDIS.REDIS_HOST,
                "port": app_settings.WEBSERVER_REDIS.REDIS_PORT,
            },
        },
        "login": {
            "enabled": app_settings.WEBSERVER_LOGIN is not None,
            "registration_invitation_required": 1
            if app_settings.WEBSERVER_LOGIN.LOGIN_REGISTRATION_INVITATION_REQUIRED
            else 0,
            "registration_confirmation_required": 1
            if app_settings.WEBSERVER_LOGIN.LOGIN_REGISTRATION_CONFIRMATION_REQUIRED
            else 0,
        },
        "smtp": {
            "sender": app_settings.WEBSERVER_EMAIL.SMTP_SENDER,
            "host": app_settings.WEBSERVER_EMAIL.SMTP_HOST,
            "port": app_settings.WEBSERVER_EMAIL.SMTP_PORT,
            "tls": int(app_settings.WEBSERVER_EMAIL.SMTP_TLS_ENABLED),
            "username": str(app_settings.WEBSERVER_EMAIL.SMTP_USERNAME),
            "password": str(
                app_settings.WEBSERVER_EMAIL.SMTP_PASSWORD
                and app_settings.WEBSERVER_EMAIL.SMTP_PASSWORD.get_secret_value()
            ),
        },
        "storage": {
            "enabled": app_settings.WEBSERVER_STORAGE is not None,
            "host": app_settings.WEBSERVER_STORAGE.STORAGE_HOST,
            "port": app_settings.WEBSERVER_STORAGE.STORAGE_PORT,
            "version": app_settings.WEBSERVER_STORAGE.STORAGE_VTAG,
        },
        "catalog": {
            "enabled": app_settings.WEBSERVER_CATALOG is not None,
            "host": app_settings.WEBSERVER_CATALOG.CATALOG_HOST,
            "port": app_settings.WEBSERVER_CATALOG.CATALOG_PORT,
            "version": app_settings.WEBSERVER_CATALOG.CATALOG_VTAG,
        },
        "rest": {"version": app_settings.API_VTAG, "enabled": True},
        "projects": {"enabled": True},
        "session": {
            "secret_key": app_settings.WEBSERVER_SESSION_SECRET_KEY.get_secret_value()
        },
        "activity": {
            "enabled": app_settings.WEBSERVER_PROMETHEUS is not None,
            "prometheus_host": app_settings.WEBSERVER_PROMETHEUS.origin,
            "prometheus_port": app_settings.WEBSERVER_PROMETHEUS.PROMETHEUS_PORT,
            "prometheus_api_version": app_settings.WEBSERVER_PROMETHEUS.PROMETHEUS_VTAG,
        },
        "clusters": {"enabled": True},
        "computation": {"enabled": True},
        "diagnostics": {"enabled": True},
        "director-v2": {"enabled": app_settings.WEBSERVER_DIRECTOR_V2 is not None},
        "exporter": {"enabled": True},
        "groups": {"enabled": True},
        "meta_modeling": {"enabled": True},
        "products": {"enabled": True},
        "publications": {"enabled": True},
        "remote_debug": {"enabled": True},
        "security": {"enabled": True},
        "statics": {"enabled": True},
        "studies_access": {
            "enabled": True
        },  # app_settings.WEBSERVER_STUDIES_ACCESS_ENABLED did not apply
        "studies_dispatcher": {
            "enabled": True  # app_settings.WEBSERVER_STUDIES_ACCESS_ENABLED did not apply
        },
        "tags": {"enabled": True},
        "users": {"enabled": True},
        "version_control": {"enabled": True},
    }


def test_settings_constructs(app_settings: ApplicationSettings):
    assert "vcs_url" in app_settings.public_dict()
    assert (
        app_settings.public_dict()["vcs_url"]
        == "git@github.com:ITISFoundation/osparc-simcore.git"
    )

    assert "app_name" in app_settings.public_dict()
    assert "api_version" in app_settings.public_dict()


def test_settings_to_client_statics(app_settings: ApplicationSettings):
    statics = app_settings.to_client_statics()

    # all key in camelcase
    assert all(
        key[0] == key[0].lower() and "_" not in key and key.lower() != key
        for key in statics.keys()
    ), f"Got {list(statics.keys())}"

    # special alias
    assert statics["stackName"] == "master-simcore"

    # can jsonify
    print(json.dumps(statics))


def test_avoid_sensitive_info_in_public(app_settings: ApplicationSettings):
    # avoids display of sensitive info
    assert not any("pass" in key for key in app_settings.public_dict().keys())
    assert not any("token" in key for key in app_settings.public_dict().keys())
    assert not any("secret" in key for key in app_settings.public_dict().keys())
