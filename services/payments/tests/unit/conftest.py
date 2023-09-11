# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import AsyncIterator

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_payments.core.application import create_app


@pytest.fixture
def app(app_environment: EnvVarsDict) -> FastAPI:
    """Inits app on a light environment"""
    return create_app()


@pytest.fixture
async def initialized_app(app: FastAPI) -> AsyncIterator[FastAPI]:
    """Inits app on a light environment"""
    async with LifespanManager(
        app,
        startup_timeout=10,
        shutdown_timeout=10,
    ):
        yield app
