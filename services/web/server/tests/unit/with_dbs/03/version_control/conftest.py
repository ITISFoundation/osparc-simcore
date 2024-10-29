# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest import mock
from uuid import UUID

import aiohttp
import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_nodes import Node
from models_library.services_resources import ServiceResourcesDict
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pytest_mock import MockerFixture
from pytest_simcore.helpers.faker_factories import random_project
from pytest_simcore.helpers.webserver_login import UserInfoDict
from pytest_simcore.helpers.webserver_projects import NewProject
from servicelib.aiohttp import status
from simcore_postgres_database.models.projects_version_control import (
    projects_vc_repos,
    projects_vc_snapshots,
)
from simcore_service_webserver._meta import API_VTAG as VX
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.db.plugin import APP_AIOPG_ENGINE_KEY
from simcore_service_webserver.log import setup_logging
from simcore_service_webserver.projects.db import ProjectDBAPI
from simcore_service_webserver.projects.models import ProjectDict
from tenacity.asyncio import AsyncRetrying
from tenacity.stop import stop_after_delay


@pytest.fixture
def user_role() -> UserRole:
    return UserRole.USER


@pytest.fixture
def fake_project(faker: Faker) -> ProjectDict:
    # API model project data
    suffix = faker.word()
    return random_project(
        name=f"{__file__}-project",
        workbench={
            faker.uuid4(): {
                "key": f"simcore/services/comp/test_{__name__}_{suffix}",
                "version": "1.2.3",
                "label": f"test_{__name__}_{suffix}",
                "inputs": {"x": faker.pyint(), "y": faker.pyint()},
            }
        },
    )


@pytest.fixture
def catalog_subsystem_mock_override(
    catalog_subsystem_mock: Callable[[list[ProjectDict]], None],
    fake_project: ProjectDict,
) -> None:
    catalog_subsystem_mock([fake_project])


@pytest.fixture
def app_cfg(
    default_app_cfg,
    unused_tcp_port_factory,
    catalog_subsystem_mock_override: None,
    monkeypatch,
) -> dict[str, Any]:
    """App's configuration used for every test in this module

    NOTE: Overrides services/web/server/tests/unit/with_dbs/conftest.py::app_cfg to influence app setup
    """
    cfg = deepcopy(default_app_cfg)

    monkeypatch.setenv("WEBSERVER_DEV_FEATURES_ENABLED", "1")

    cfg["main"]["port"] = unused_tcp_port_factory()
    cfg["main"]["studies_access_enabled"] = True

    exclude = {
        "activity",
        "clusters",
        "computation",
        "diagnostics",
        "groups",
        "publications",
        "garbage_collector",
        "smtp",
        "socketio",
        "storage",
        "studies_dispatcher",
        "tags",
        "tracing",
    }
    include = {
        "catalog",
        "db",
        "login",
        "products",
        "projects",
        "resource_manager",
        "rest",
        "users",
        "version_control",  # MODULE UNDER TEST
    }

    assert include.intersection(exclude) == set()

    for section in include:
        cfg[section]["enabled"] = True
    for section in exclude:
        cfg[section]["enabled"] = False

    # NOTE: To see logs, use pytest -s --log-cli-level=DEBUG
    setup_logging(
        level=logging.DEBUG, log_format_local_dev_enabled=True, logger_filter_mapping={}
    )

    # Enforces smallest GC in the background task
    cfg["resource_manager"]["garbage_collection_interval_seconds"] = 1

    return cfg


@pytest.fixture
async def user_id(logged_user: UserInfoDict) -> UserID:
    return logged_user["id"]


@pytest.fixture()
def project_uuid(user_project: ProjectDict) -> ProjectID:
    return UUID(user_project["uuid"])


@pytest.fixture
async def user_project(
    client: TestClient,
    fake_project: ProjectDict,
    user_id: int,
    tests_data_dir: Path,
    osparc_product_name: str,
) -> AsyncIterator[ProjectDict]:
    # pylint: disable=no-value-for-parameter

    async with NewProject(
        fake_project,
        client.app,
        user_id=user_id,
        tests_data_dir=tests_data_dir,
        product_name=osparc_product_name,
    ) as project:
        yield project

        # cleanup repos
        assert client.app
        engine = client.app[APP_AIOPG_ENGINE_KEY]
        async with engine.acquire() as conn:
            # cascade deletes everything except projects_vc_snapshot
            await conn.execute(projects_vc_repos.delete())
            await conn.execute(projects_vc_snapshots.delete())


@pytest.fixture
def request_update_project(
    logged_user: UserInfoDict,
    faker: Faker,
    mocker: MockerFixture,
) -> Callable[[TestClient, UUID], Awaitable]:
    mocker.patch(
        "simcore_service_webserver.projects._nodes_handlers.projects_api.is_service_deprecated",
        autospec=True,
        return_value=False,
    )
    mocker.patch(
        "simcore_service_webserver.projects._nodes_handlers.projects_api.catalog_client.get_service_resources",
        autospec=True,
        return_value=ServiceResourcesDict(),
    )
    mocker.patch(
        "simcore_service_webserver.director_v2.api.list_dynamic_services",
        return_value=[],
    )

    async def _go(client: TestClient, project_uuid: UUID) -> None:
        resp: aiohttp.ClientResponse = await client.get(f"{VX}/projects/{project_uuid}")

        assert resp.status == 200
        body = await resp.json()
        assert body

        project = body["data"]

        # remove all the nodes first
        assert client.app
        for node_id in project.get("workbench", {}):
            delete_node_url = client.app.router["delete_node"].url_for(
                project_id=f"{project_uuid}", node_id=node_id
            )
            response = await client.delete(f"{delete_node_url}")
            assert response.status == status.HTTP_204_NO_CONTENT

        # add a node
        node_id = faker.uuid4()
        node = Node.parse_obj(
            {
                "key": f"simcore/services/comp/test_{__name__}",
                "version": "1.0.0",
                "label": f"test_{__name__}",
                "inputs": {"x": faker.pyint(), "y": faker.pyint()},
            }
        )

        create_node_url = client.app.router["create_node"].url_for(
            project_id=f"{project_uuid}"
        )
        response = await client.post(
            f"{create_node_url}",
            json={
                "service_key": node.key,
                "service_version": node.version,
                "service_id": f"{node_id}",
            },
        )
        assert response.status == status.HTTP_201_CREATED
        project["workbench"] = {node_id: jsonable_encoder(node)}

        db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(client.app)
        project.pop("state")
        await db.replace_project(
            project,
            logged_user["id"],
            project_uuid=project["uuid"],
            product_name="osparc",
        )

    return _go


@pytest.fixture
async def request_delete_project(
    logged_user: UserInfoDict,
    mocker: MockerFixture,
) -> AsyncIterator[Callable[[TestClient, UUID], Awaitable]]:
    director_v2_api_delete_pipeline: mock.AsyncMock = mocker.patch(
        "simcore_service_webserver.projects.projects_api.director_v2_api.delete_pipeline",
        autospec=True,
    )
    dynamic_scheduler_api_stop_dynamic_services_in_project: mock.AsyncMock = mocker.patch(
        "simcore_service_webserver.projects.projects_api.dynamic_scheduler_api.stop_dynamic_services_in_project",
        autospec=True,
    )
    fire_and_forget_call_to_storage: mock.Mock = mocker.patch(
        "simcore_service_webserver.projects._crud_api_delete.delete_data_folders_of_project",
        autospec=True,
    )

    async def _go(client: TestClient, project_uuid: UUID) -> None:
        resp: aiohttp.ClientResponse = await client.delete(
            f"{VX}/projects/{project_uuid}"
        )
        assert resp.status == 204

    yield _go

    # ensure the call to delete data was completed
    async for attempt in AsyncRetrying(reraise=True, stop=stop_after_delay(20)):
        with attempt:
            director_v2_api_delete_pipeline.assert_called()
            dynamic_scheduler_api_stop_dynamic_services_in_project.assert_awaited()
            fire_and_forget_call_to_storage.assert_called()
