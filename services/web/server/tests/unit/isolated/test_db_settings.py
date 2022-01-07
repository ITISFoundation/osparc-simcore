# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import os
from typing import Any, Dict

import pytest
from simcore_service_webserver.application_settings import ApplicationSettings
from simcore_service_webserver.db_settings import PostgresSettings


@pytest.fixture
def mock_service_environ(mock_env_devel_environment, monkeypatch):
    """
    Mocks environment produce by

    - .env-devel + docker-compose service environs
        hostname: "{{.Node.Hostname}}-{{.Service.Name}}-{{.Task.Slot}}"

        environment:
            - CATALOG_HOST=${CATALOG_HOST:-catalog}
            - CATALOG_PORT=${CATALOG_PORT:-8000}
            - DIAGNOSTICS_MAX_AVG_LATENCY=10
            - DIAGNOSTICS_MAX_TASK_DELAY=30
            - DIRECTOR_HOST=${DIRECTOR_HOST:-director}
            - DIRECTOR_PORT=${DIRECTOR_PORT:-8080}
            - DIRECTOR_V2_HOST=${DIRECTOR_V2_HOST:-director-v2}
            - DIRECTOR_V2_PORT=${DIRECTOR_V2_PORT:-8000}
            - STORAGE_HOST=${STORAGE_HOST:-storage}
            - STORAGE_PORT=${STORAGE_PORT:-8080}
            - SWARM_STACK_NAME=${SWARM_STACK_NAME:-simcore}
            - WEBSERVER_LOGLEVEL=${LOG_LEVEL:-WARNING}
        env_file:
            - ../.env
    - Dockerfile

    """
    monkeypatch.setenv("HOSTNAME", "Node.Hostname-Service.Name-Task.Slot")

    def monkeypatch_setenv_default(name, default):
        if name not in os.environ:
            monkeypatch.setenv(name, default)

    # r'- ([A-Z2_]+)=\$\{\1:-([\w-]+)\}'
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


def test_config_to_settings(mock_service_environ):
    old_cfg = {
        "db": {
            "postgres": {
                "database": "simcoredb",
                # "endpoint": "postgres:5432",
                "host": "postgres",
                "maxsize": 50,
                "minsize": 1,
                "password": "adminadmin",
                "port": 5432,
                "user": "scu",
            }
        }
    }

    settings = PostgresSettings.create_from_envs()

    print(settings.json(indent=2))
    print(settings.json(indent=2, exclude_unset=True))

    assert old_cfg["db"]["postgres"] == {
        "database": settings.POSTGRES_DB,
        # "endpoint": settings.dsn,
        "host": settings.POSTGRES_HOST,
        "maxsize": settings.POSTGRES_MAXSIZE,
        "minsize": settings.POSTGRES_MINSIZE,
        "password": settings.POSTGRES_PASSWORD.get_secret_value(),
        "port": settings.POSTGRES_PORT,
        "user": settings.POSTGRES_USER,
    }

    app_settings = ApplicationSettings.create_from_envs()
    assert app_settings.WEBSERVER_POSTGRES == settings
