# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from pytest_mock import MockerFixture
from simcore_service_director_v2.modules.dynamic_sidecar.module_setup import (
    configure_dynamic_sidecar,
)


@pytest.fixture
def app(mocker: MockerFixture) -> FastAPI:
    # long_running_tasks client/server plugin wiring is exercised elsewhere: stub it out here
    mocker.patch(
        "simcore_service_director_v2.modules.dynamic_sidecar.module_setup.long_running_tasks_client.configure_client",
        autospec=True,
    )
    mocker.patch(
        "simcore_service_director_v2.modules.dynamic_sidecar.module_setup.long_running_tasks_server.configure_server",
        autospec=True,
    )
    app = FastAPI()
    app.state.settings = Mock()
    return app


async def test_partial_startup_failure_only_tears_down_started_resources(app: FastAPI, mocker: MockerFixture):
    """If the scheduler fails to start, the already-started api_client must still be torn down."""
    api_client_setup = mocker.patch(
        "simcore_service_director_v2.modules.dynamic_sidecar.module_setup.api_client.setup", autospec=True
    )
    api_client_shutdown = mocker.patch(
        "simcore_service_director_v2.modules.dynamic_sidecar.module_setup.api_client.shutdown", autospec=True
    )
    scheduler_setup = mocker.patch(
        "simcore_service_director_v2.modules.dynamic_sidecar.module_setup.scheduler.setup_scheduler",
        autospec=True,
        side_effect=RuntimeError("boom"),
    )
    scheduler_shutdown = mocker.patch(
        "simcore_service_director_v2.modules.dynamic_sidecar.module_setup.scheduler.shutdown_scheduler",
        autospec=True,
    )

    app_lifespan: LifespanManager = LifespanManager()
    configure_dynamic_sidecar(app, app_lifespan)

    with pytest.raises(RuntimeError, match="boom"):
        async with app_lifespan(app):
            pytest.fail("lifespan should have failed to start")

    api_client_setup.assert_called_once_with(app)
    scheduler_setup.assert_called_once_with(app)

    api_client_shutdown.assert_called_once_with(app)
    scheduler_shutdown.assert_not_called()


async def test_full_startup_and_shutdown_order(app: FastAPI, mocker: MockerFixture):
    calls: list[str] = []

    def _record(name: str):
        async def _fct(_app: FastAPI) -> None:
            calls.append(name)

        return _fct

    mocker.patch(
        "simcore_service_director_v2.modules.dynamic_sidecar.module_setup.api_client.setup",
        side_effect=_record("api_client.setup"),
    )
    mocker.patch(
        "simcore_service_director_v2.modules.dynamic_sidecar.module_setup.api_client.shutdown",
        side_effect=_record("api_client.shutdown"),
    )
    mocker.patch(
        "simcore_service_director_v2.modules.dynamic_sidecar.module_setup.scheduler.setup_scheduler",
        side_effect=_record("scheduler.setup_scheduler"),
    )
    mocker.patch(
        "simcore_service_director_v2.modules.dynamic_sidecar.module_setup.scheduler.shutdown_scheduler",
        side_effect=_record("scheduler.shutdown_scheduler"),
    )

    app_lifespan: LifespanManager = LifespanManager()
    configure_dynamic_sidecar(app, app_lifespan)

    async with app_lifespan(app):
        pass

    assert calls == [
        "api_client.setup",
        "scheduler.setup_scheduler",
        "scheduler.shutdown_scheduler",
        "api_client.shutdown",
    ]
