# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import AsyncIterator
from typing import Annotated, Any

import pytest
import servicelib.fastapi.postgres_lifespan
from asgi_lifespan import LifespanManager as ASGILifespanManager
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from pydantic import Field
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.fastapi.postgres_lifespan import (
    PostgresLifespanStateKeys,
    postgres_lifespan,
)
from settings_library.application import BaseApplicationSettings
from settings_library.postgres import PostgresSettings


@pytest.fixture
def mock_create_async_engine_and_database_ready(mocker: MockerFixture) -> MockType:
    return mocker.patch.object(
        servicelib.fastapi.postgres_lifespan,
        "create_async_engine_and_database_ready",
        return_value=mocker.AsyncMock(),
    )


@pytest.fixture
def app_environment(monkeypatch: pytest.MonkeyPatch) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch, PostgresSettings.model_json_schema()["examples"][0]
    )


@pytest.fixture
def app_lifespan(
    app_environment: EnvVarsDict,
    mock_create_async_engine_and_database_ready: MockType,
) -> LifespanManager:
    assert app_environment

    class AppSettings(BaseApplicationSettings):
        CATALOG_POSTGRES: Annotated[
            PostgresSettings,
            Field(json_schema_extra={"auto_default_from_env": True}),
        ]

    async def my_app_settings(app: FastAPI) -> AsyncIterator[State]:
        app.state.settings = AppSettings.create_from_envs()

        yield {
            PostgresLifespanStateKeys.POSTGRES_SETTINGS: app.state.settings.CATALOG_POSTGRES
        }

    async def my_database_setup(app: FastAPI, state: State) -> AsyncIterator[State]:
        app.state.my_db_engine = state[PostgresLifespanStateKeys.POSTGRES_ASYNC_ENGINE]

        yield {}

    # compose lifespans
    app_lifespan = LifespanManager()
    app_lifespan.add(my_app_settings)

    postgres_lifespan.add(my_database_setup)
    app_lifespan.include(postgres_lifespan)

    return app_lifespan


async def test_setup_postgres_database_in_an_app(
    is_pdb_enabled: bool,
    app_environment: EnvVarsDict,
    mock_create_async_engine_and_database_ready: MockType,
    app_lifespan: LifespanManager,
):

    app = FastAPI(lifespan=app_lifespan)

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
        assert (
            PostgresLifespanStateKeys.POSTGRES_ASYNC_ENGINE
            in asgi_manager._state  # noqa: SLF001
        )
        assert app.state.my_db_engine
        assert (
            app.state.my_db_engine
            == asgi_manager._state[  # noqa: SLF001
                PostgresLifespanStateKeys.POSTGRES_ASYNC_ENGINE
            ]
        )

        assert (
            app.state.my_db_engine
            == mock_create_async_engine_and_database_ready.return_value
        )

    # Verify that the engine was disposed
    async_engine: Any = mock_create_async_engine_and_database_ready.return_value
    async_engine.dispose.assert_called_once()


async def test_setup_postgres_database_dispose_engine_on_failure(
    is_pdb_enabled: bool,
    app_environment: EnvVarsDict,
    mock_create_async_engine_and_database_ready: MockType,
    app_lifespan: LifespanManager,
):
    expected_msg = "my_faulty_setup error"

    def raise_error():
        raise RuntimeError(expected_msg)

    @app_lifespan.add
    async def my_faulty_setup(app: FastAPI, state: State) -> AsyncIterator[State]:
        assert PostgresLifespanStateKeys.POSTGRES_ASYNC_ENGINE in state
        raise_error()
        yield {}

    app = FastAPI(lifespan=app_lifespan)

    with pytest.raises(RuntimeError, match=expected_msg):
        async with ASGILifespanManager(
            app,
            startup_timeout=None if is_pdb_enabled else 10,
            shutdown_timeout=None if is_pdb_enabled else 10,
        ):
            ...

    # Verify that the engine was disposed even if error happend
    async_engine: Any = mock_create_async_engine_and_database_ready.return_value
    async_engine.dispose.assert_called_once()
