# pylint:disable=redefined-outer-name

"""Benchmarks for `settings_library`

Every service builds its settings from environment variables at startup, and
`model_dump_with_secrets` is used to expose/serialize them (e.g. in the
diagnostics endpoints or when passing settings to a sidecar).
"""

from typing import Annotated

import pytest
from common_library.serialization import model_dump_with_secrets
from pydantic import Field
from settings_library.base import BaseCustomSettings
from settings_library.postgres import PostgresSettings
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings


class _ApplicationSettings(BaseCustomSettings):
    """Mimics the composed settings of a simcore service"""

    APP_NAME: str
    APP_LOG_LEVEL: str = "INFO"

    APP_POSTGRES: Annotated[PostgresSettings, Field(json_schema_extra={"auto_default_from_env": True})]
    APP_RABBIT: Annotated[RabbitSettings, Field(json_schema_extra={"auto_default_from_env": True})]
    APP_REDIS: Annotated[RedisSettings, Field(json_schema_extra={"auto_default_from_env": True})]


_ENVIRONMENT: dict[str, str] = {
    "APP_NAME": "benchmark-service",
    "POSTGRES_HOST": "postgres",
    "POSTGRES_PORT": "5432",
    "POSTGRES_USER": "scu",
    "POSTGRES_PASSWORD": "adminadmin",
    "POSTGRES_DB": "simcoredb",
    "POSTGRES_MAX_POOLSIZE": "10",
    "POSTGRES_MAX_OVERFLOW": "20",
    "RABBIT_HOST": "rabbit",
    "RABBIT_PORT": "5672",
    "RABBIT_USER": "admin",
    "RABBIT_SECURE": "0",
    "RABBIT_PASSWORD": "adminadmin",
    "REDIS_HOST": "redis",
    "REDIS_PORT": "6379",
    "REDIS_SECURE": "0",
    "REDIS_USER": "null",
    "REDIS_PASSWORD": "adminadmin",
}


@pytest.fixture
def _with_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in _ENVIRONMENT.items():
        monkeypatch.setenv(key, value)


@pytest.mark.usefixtures("_with_environment")
def test_postgres_settings_create_from_env(benchmark):
    settings = benchmark(PostgresSettings.create_from_envs)
    assert settings.POSTGRES_HOST == "postgres"


@pytest.mark.usefixtures("_with_environment")
def test_application_settings_create_from_env(benchmark):
    settings = benchmark(_ApplicationSettings.create_from_envs)
    assert settings.APP_NAME == "benchmark-service"


@pytest.mark.usefixtures("_with_environment")
def test_application_settings_dump_with_secrets(benchmark):
    settings = _ApplicationSettings.create_from_envs()
    result = benchmark(lambda: model_dump_with_secrets(settings, show_secrets=False))
    assert result["APP_NAME"] == "benchmark-service"


@pytest.mark.usefixtures("_with_environment")
def test_application_settings_json_schema(benchmark):
    schema = benchmark(_ApplicationSettings.model_json_schema)
    assert schema["title"]


@pytest.mark.usefixtures("_with_environment")
def test_postgres_settings_dsn_with_query(benchmark):
    settings = PostgresSettings.create_from_envs()

    def _build_dsns() -> int:
        return sum(len(settings.dsn_with_query(f"app-{i}", suffix=None)) for i in range(50))

    assert benchmark(_build_dsns) > 0
