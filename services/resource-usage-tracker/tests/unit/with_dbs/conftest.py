from typing import AsyncIterable
from unittest import mock

import httpx
import pytest
import sqlalchemy as sa
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from pytest import MonkeyPatch
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from simcore_service_resource_usage_tracker.core.application import create_app
from simcore_service_resource_usage_tracker.core.settings import ApplicationSettings

# @pytest.fixture()
# async def products_names(
#     sqlalchemy_async_engine: AsyncEngine,
# ) -> AsyncIterator[list[str]]:
#     """Inits products db table and returns product names"""
#     data = [
#         # already upon creation: ("osparc", r"([\.-]{0,1}osparc[\.-])"),
#         ("s4l", r"(^s4l[\.-])|(^sim4life\.)|(^api.s4l[\.-])|(^api.sim4life\.)"),
#         ("tis", r"(^tis[\.-])|(^ti-solutions\.)"),
#     ]

#     # pylint: disable=no-value-for-parameter

#     async with sqlalchemy_async_engine.begin() as conn:
#         # NOTE: The 'default' dialect with current database version settings does not support in-place multirow inserts
#         for n, (name, regex) in enumerate(data):
#             stmt = products.insert().values(name=name, host_regex=regex, priority=n)
#             await conn.execute(stmt)

#     names = [
#         "osparc",
#     ] + [items[0] for items in data]

#     yield names

#     async with sqlalchemy_async_engine.begin() as conn:
#         await conn.execute(products.delete())


# @pytest.fixture
# def _app(
#     postgres_db: sa.engine.Engine,
#     postgres_host_config: dict[str, str],
#     app_settings: ApplicationSettings,
#     monkeypatch: MonkeyPatch,
#     mocker: MockerFixture,
#     service_test_environ: None,
#     products_names: list[str],
# ) -> Iterable[FastAPI]:
#     print("database started:", postgres_host_config)
#     print("database w/products in table:", products_names)

#     app = create_app(app_settings)
#     yield app


# @pytest.fixture
# def client(app: FastAPI) -> Iterator[TestClient]:
#     with TestClient(app) as cli:
#         # Note: this way we ensure the events are run in the application
#         yield cli


@pytest.fixture(scope="function")
def mock_env(monkeypatch: MonkeyPatch) -> EnvVarsDict:
    """This is the base mock envs used to configure the app.

    Do override/extend this fixture to change configurations
    """
    env_vars: EnvVarsDict = {
        "SC_BOOT_MODE": "production",
        "POSTGRES_CLIENT_NAME": "postgres_test_client",
    }
    setenvs_from_dict(monkeypatch, env_vars)
    return env_vars


@pytest.fixture(scope="function")
async def initialized_app(
    mock_env: EnvVarsDict,
    postgres_db: sa.engine.Engine,
    postgres_host_config: dict[str, str],
) -> AsyncIterable[FastAPI]:
    settings = ApplicationSettings.create_from_envs()
    app = create_app(settings)
    async with LifespanManager(app):
        yield app


@pytest.fixture(scope="function")
async def async_client(initialized_app: FastAPI) -> AsyncIterable[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        app=initialized_app,
        base_url="http://resource-usage-tracker.testserver.io",
        headers={"Content-Type": "application/json"},
    ) as client:
        yield client


@pytest.fixture
def mocked_prometheus(mocker: MockerFixture) -> mock.Mock:
    mocked_get_prometheus_api_client = mocker.patch(
        "simcore_service_resource_usage_tracker.resource_tracker_core.get_prometheus_api_client",
        autospec=True,
    )
    return mocked_get_prometheus_api_client
