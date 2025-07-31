# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import logging
from collections.abc import AsyncIterable
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from aioresponses import aioresponses
from models_library.products import ProductName
from pytest_mock import MockerFixture
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_parametrizations import MockedStorageSubsystem
from pytest_simcore.helpers.webserver_projects import new_project
from pytest_simcore.helpers.webserver_users import NewUser, UserInfoDict
from simcore_service_webserver.projects.models import ProjectDict

_logger = logging.getLogger(__name__)


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch, {"WEBSERVER_DEV_FEATURES_ENABLED": "1"}
    )


@pytest.fixture
async def other_user(
    client: TestClient, logged_user: UserInfoDict
) -> AsyncIterable[UserInfoDict]:
    # new user different from logged_user
    async with NewUser(
        {
            "name": f"other_user_than_{logged_user['name']}",
            "role": "USER",
        },
        client.app,
    ) as user:
        yield user


@pytest.fixture
async def other_user_project(
    client: TestClient,
    fake_project: ProjectDict,
    other_user: UserInfoDict,
    tests_data_dir: Path,
    osparc_product_name: ProductName,
) -> AsyncIterable[ProjectDict]:
    async with new_project(
        fake_project,
        client.app,
        user_id=other_user["id"],
        product_name=osparc_product_name,
        tests_data_dir=tests_data_dir,
    ) as project:
        yield project


@pytest.fixture
def mocked_catalog(
    user_project: ProjectDict,
): ...


@pytest.fixture
def mocked_director_v2(director_v2_service_mock: aioresponses): ...


@pytest.fixture
def mocked_storage(storage_subsystem_mock: MockedStorageSubsystem): ...


@pytest.fixture
def with_disabled_background_task_to_prune_trash(mocker: MockerFixture) -> None:
    async def _empty_lifespan(app: web.Application):
        with log_context(
            logging.INFO, "Fake background_task_to_prune_trash event", logger=_logger
        ):
            yield

    mocker.patch(
        "simcore_service_webserver.garbage_collector._tasks_trash.create_background_task_to_prune_trash",
        autospec=True,
        return_value=_empty_lifespan,
    )
