# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import pytest
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from pytest_mock import MockerFixture
from simcore_service_director_v2.modules.comp_scheduler import configure_comp_scheduler


async def test_partial_startup_failure_only_tears_down_started_resources(mocker: MockerFixture):
    """If `setup_worker` fails, the releaser (already started) must be shut down while the
    manager (never started) must not."""
    setup_releaser = mocker.patch("simcore_service_director_v2.modules.comp_scheduler.setup_releaser", autospec=True)
    shutdown_releaser = mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler.shutdown_releaser", autospec=True
    )
    setup_worker = mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler.setup_worker",
        autospec=True,
        side_effect=RuntimeError("boom"),
    )
    shutdown_worker = mocker.patch("simcore_service_director_v2.modules.comp_scheduler.shutdown_worker", autospec=True)
    setup_manager = mocker.patch("simcore_service_director_v2.modules.comp_scheduler.setup_manager", autospec=True)
    shutdown_manager = mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler.shutdown_manager", autospec=True
    )

    app = FastAPI()
    app_lifespan: LifespanManager = LifespanManager()
    configure_comp_scheduler(app_lifespan)

    with pytest.raises(RuntimeError, match="boom"):
        async with app_lifespan(app):
            pytest.fail("lifespan should have failed to start")

    setup_releaser.assert_called_once_with(app)
    setup_worker.assert_called_once_with(app)
    setup_manager.assert_not_called()

    shutdown_releaser.assert_called_once_with(app)
    shutdown_worker.assert_not_called()
    shutdown_manager.assert_not_called()


async def test_full_startup_and_shutdown_order(mocker: MockerFixture):
    calls: list[str] = []

    def _record(name: str):
        async def _fct(_app: FastAPI) -> None:
            calls.append(name)

        return _fct

    mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler.setup_releaser",
        side_effect=_record("setup_releaser"),
    )
    mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler.setup_worker",
        side_effect=_record("setup_worker"),
    )
    mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler.setup_manager",
        side_effect=_record("setup_manager"),
    )
    mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler.shutdown_manager",
        side_effect=_record("shutdown_manager"),
    )
    mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler.shutdown_worker",
        side_effect=_record("shutdown_worker"),
    )
    mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler.shutdown_releaser",
        side_effect=_record("shutdown_releaser"),
    )

    app = FastAPI()
    app_lifespan: LifespanManager = LifespanManager()
    configure_comp_scheduler(app_lifespan)

    async with app_lifespan(app):
        pass

    assert calls == [
        "setup_releaser",
        "setup_worker",
        "setup_manager",
        "shutdown_manager",
        "shutdown_worker",
        "shutdown_releaser",
    ]
