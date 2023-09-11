# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import AsyncIterator, Callable

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_payments.core.application import create_app


@pytest.fixture
def disable_rabbitmq_service(mocker: MockerFixture) -> Callable:
    def _doit():
        # The following moduls are affected if rabbitmq is not in place
        mocker.patch("simcore_service_payments.core.application.setup_rabbitmq")
        mocker.patch("simcore_service_payments.core.application.setup_rpc_api_routes")

    return _doit


@pytest.fixture
async def app(app_environment: EnvVarsDict) -> AsyncIterator[FastAPI]:
    test_app = create_app()
    async with LifespanManager(
        test_app,
        startup_timeout=10,
        shutdown_timeout=10,
    ):
        yield test_app
