# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import pytest
from aiohttp import web
from pytest_mock import MockerFixture
from servicelib.aiohttp.observer import (
    emit,
    registed_observers_report,
    register_observer,
    setup_observer_registry,
)


@pytest.fixture
def app() -> web.Application:
    _app = web.Application()
    setup_observer_registry(_app)
    return _app


async def test_observer(mocker: MockerFixture, app: web.Application):
    # register a couroutine as callback function
    cb_function = mocker.AsyncMock(return_value=None)

    register_observer(app, cb_function, event="my_test_event")

    registed_observers_report(app)

    await emit(app, "my_invalid_test_event")
    cb_function.assert_not_called()

    await emit(app, "my_test_event")
    cb_function.assert_called()
