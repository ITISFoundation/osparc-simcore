# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import logging
from collections.abc import AsyncIterator
from typing import Any

import pytest
from asgi_lifespan import LifespanManager as ASGILifespanManager
from common_library.errors_classes import OsparcErrorMixin
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from pytest_mock import MockerFixture
from pytest_simcore.helpers.logging_tools import log_context
from servicelib.fastapi.lifespan_utils import combine_lifespans


async def test_multiple_lifespan_managers(capsys: pytest.CaptureFixture):
    async def database_lifespan(app: FastAPI) -> AsyncIterator[State]:
        _ = app
        print("setup DB")
        yield {}
        print("shutdown  DB")

    async def cache_lifespan(app: FastAPI) -> AsyncIterator[State]:
        _ = app
        print("setup CACHE")
        yield {}
        print("shutdown CACHE")

    app = FastAPI(lifespan=combine_lifespans(database_lifespan, cache_lifespan))

    capsys.readouterr()

    async with ASGILifespanManager(app):
        messages = capsys.readouterr().out

        assert "setup DB" in messages
        assert "setup CACHE" in messages
        assert "shutdown  DB" not in messages
        assert "shutdown CACHE" not in messages

    messages = capsys.readouterr().out

    assert "setup DB" not in messages
    assert "setup CACHE" not in messages
    assert "shutdown  DB" in messages
    assert "shutdown CACHE" in messages


@pytest.fixture
def postgres_lifespan() -> LifespanManager:
    lifespan_manager = LifespanManager()

    @lifespan_manager.add
    async def _setup_postgres_sync_engine(_) -> AsyncIterator[State]:
        with log_context(logging.INFO, "postgres_sync_engine"):
            # pass state to children
            yield {"postgres": {"engine": "Some Engine"}}

    @lifespan_manager.add
    async def _setup_postgres_async_engine(_, state: State) -> AsyncIterator[State]:
        with log_context(logging.INFO, "postgres_async_engine"):
            # pass state to children

            state["postgres"].update(aengine="Some Async Engine")
            yield state

    return lifespan_manager


@pytest.fixture
def rabbitmq_lifespan() -> LifespanManager:
    lifespan_manager = LifespanManager()

    @lifespan_manager.add
    async def _setup_rabbitmq(app: FastAPI) -> AsyncIterator[State]:
        with log_context(logging.INFO, "rabbitmq"):

            with pytest.raises(AttributeError, match="rabbitmq_rpc_server"):
                _ = app.state.rabbitmq_rpc_server

            # pass state to children
            yield {"rabbitmq_rpc_server": "Some RabbitMQ RPC Server"}

    return lifespan_manager


async def test_app_lifespan_composition(
    postgres_lifespan: LifespanManager, rabbitmq_lifespan: LifespanManager
):
    # The app has its own database and rpc-server to initialize
    # this is how you connect the lifespans pre-defined in servicelib

    @postgres_lifespan.add
    async def setup_database(app: FastAPI, state: State) -> AsyncIterator[State]:

        with log_context(logging.INFO, "app database"):
            assert state["postgres"] == {
                "engine": "Some Engine",
                "aengine": "Some Async Engine",
            }

            with pytest.raises(AttributeError, match="database_engine"):
                _ = app.state.database_engine

            app.state.database_engine = state["postgres"]["engine"]

            yield {}

            # tear-down stage
            assert app.state.database_engine

    @rabbitmq_lifespan.add
    async def setup_rpc_server(app: FastAPI, state: State) -> AsyncIterator[State]:
        with log_context(logging.INFO, "app rpc-server"):
            assert "rabbitmq_rpc_server" in state

            app.state.rpc_server = state["rabbitmq_rpc_server"]

            yield {}

    # Composes lifepans
    app_lifespan = LifespanManager()
    app_lifespan.include(postgres_lifespan)
    app_lifespan.include(rabbitmq_lifespan)

    app = FastAPI(lifespan=app_lifespan)
    async with ASGILifespanManager(app) as asgi_manager:

        # asgi_manage state
        assert asgi_manager._state == {  # noqa: SLF001
            "postgres": {
                "engine": "Some Engine",
                "aengine": "Some Async Engine",
            },
            "rabbitmq_rpc_server": "Some RabbitMQ RPC Server",
        }

        # app state
        assert app.state.database_engine
        assert app.state.rpc_server

    # Logs shows lifespan execution:
    #     -> postgres_sync_engine starting ...
    #             -> postgres_async_engine starting ...
    #                     -> app database starting ...
    #                             -> rabbitmq starting ...
    #                                     -> app rpc-server starting ...
    #                                     <- app rpc-server done ()
    #                             <- rabbitmq done ()
    #                     <- app database done (1ms)
    #             <- postgres_async_engine done (1ms)
    #     <- postgres_sync_engine done (1ms)


class LifespanError(OsparcErrorMixin, RuntimeError): ...


class LifespanOnStartupError(LifespanError):
    msg_template = "Failed during startup of {module}"


class LifespanOnShutdownError(LifespanError):
    msg_template = "Failed during shutdown of {module}"


@pytest.fixture
def failing_lifespan_manager(mocker: MockerFixture):
    startup_step = mocker.MagicMock()
    shutdown_step = mocker.MagicMock()
    handle_error = mocker.MagicMock()

    def raise_error():
        msg = "failing module"
        raise RuntimeError(msg)

    async def setup_failing_on_startup(app: FastAPI) -> AsyncIterator[State]:
        _name = setup_failing_on_startup.__name__

        with log_context(logging.INFO, _name):
            try:
                raise_error()
                startup_step(_name)
            except RuntimeError as exc:
                handle_error(_name, exc)
                raise LifespanOnStartupError(module=_name) from exc
            yield {}
            shutdown_step(_name)

    async def setup_failing_on_shutdown(app: FastAPI) -> AsyncIterator[State]:
        _name = setup_failing_on_shutdown.__name__

        with log_context(logging.INFO, _name):
            startup_step(_name)
            yield {}
            try:
                raise_error()
                shutdown_step(_name)
            except RuntimeError as exc:
                handle_error(_name, exc)
                raise LifespanOnShutdownError(module=_name) from exc

    return {
        "startup_step": startup_step,
        "shutdown_step": shutdown_step,
        "handle_error": handle_error,
        "setup_failing_on_startup": setup_failing_on_startup,
        "setup_failing_on_shutdown": setup_failing_on_shutdown,
    }


async def test_app_lifespan_with_error_on_startup(
    failing_lifespan_manager: dict[str, Any],
):
    app_lifespan = LifespanManager()
    app_lifespan.add(failing_lifespan_manager["setup_failing_on_startup"])
    app = FastAPI(lifespan=app_lifespan)

    with pytest.raises(LifespanOnStartupError) as err_info:
        async with ASGILifespanManager(app):
            ...

    exception = err_info.value
    assert failing_lifespan_manager["handle_error"].called
    assert not failing_lifespan_manager["startup_step"].called
    assert not failing_lifespan_manager["shutdown_step"].called
    assert exception.error_context() == {
        "module": "setup_failing_on_startup",
        "message": "Failed during startup of setup_failing_on_startup",
        "code": "RuntimeError.LifespanError.LifespanOnStartupError",
    }


async def test_app_lifespan_with_error_on_shutdown(
    failing_lifespan_manager: dict[str, Any],
):
    app_lifespan = LifespanManager()
    app_lifespan.add(failing_lifespan_manager["setup_failing_on_shutdown"])
    app = FastAPI(lifespan=app_lifespan)

    with pytest.raises(LifespanOnShutdownError) as err_info:
        async with ASGILifespanManager(app):
            ...

    exception = err_info.value
    assert failing_lifespan_manager["handle_error"].called
    assert failing_lifespan_manager["startup_step"].called
    assert not failing_lifespan_manager["shutdown_step"].called
    assert exception.error_context() == {
        "module": "setup_failing_on_shutdown",
        "message": "Failed during shutdown of setup_failing_on_shutdown",
        "code": "RuntimeError.LifespanError.LifespanOnShutdownError",
    }
