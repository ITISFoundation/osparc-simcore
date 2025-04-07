# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Annotated, Any

import pytest
from asgi_lifespan import LifespanManager as ASGILifespanManager
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from pydantic import Field
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.fastapi.postgres_lifespan import postgres_lifespan
from settings_library.application import BaseApplicationSettings
from settings_library.postgres import PostgresSettings


@pytest.fixture
def mock_create_async_engine_and_database_ready(mocker: MockerFixture) -> MockType:
    return mocker.patch(
        "servicelib.fastapi.postgres_lifespan.create_async_engine_and_database_ready",
        return_value=mocker.AsyncMock(),
    )


@pytest.fixture
def app_environment(monkeypatch: pytest.MonkeyPatch) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch, PostgresSettings.model_json_schema()["examples"][0]
    )


async def test_setup_postgres_database_in_an_app(
    is_pdb_enabled: bool,
    app_environment: EnvVarsDict,
    mock_create_async_engine_and_database_ready: MockType,
):
    assert app_environment

    @postgres_lifespan.add
    async def my_db_setup(app: FastAPI, state: State):
        app.state.my_db_engine = state["postgres.async_engine"]

        assert (
            app.state.my_db_engine
            == mock_create_async_engine_and_database_ready.return_value
        )

        yield

    # compose lifespans
    app_lifespan = LifespanManager()
    app_lifespan.include(postgres_lifespan)

    # define app
    app = FastAPI(lifespan=app_lifespan)

    # settings
    class AppSettings(BaseApplicationSettings):
        CATALOG_POSTGRES: Annotated[
            PostgresSettings,
            Field(json_schema_extra={"auto_default_from_env": True}),
        ]

    app.state.settings = AppSettings.create_from_envs()

    async with ASGILifespanManager(
        app,
        startup_timeout=None if is_pdb_enabled else 10,
        shutdown_timeout=None if is_pdb_enabled else 10,
    ) as asgi_manager:
        # Verify that the async engine was created
        mock_create_async_engine_and_database_ready.assert_called_once_with(
            app.state.settings.CATALOG_POSTGRES
        )

        # Verify that the async engine is in the lifespan manager state
        assert "postgres.async_engine" in asgi_manager._state  # noqa: SLF001
        assert app.state.my_db_engine
        assert (
            app.state.my_db_engine
            == asgi_manager._state["postgres.async_engine"]  # noqa: SLF001
        )

    # Verify that the engine was disposed
    async_engine: Any = mock_create_async_engine_and_database_ready.return_value
    async_engine.dispose.assert_called_once()
