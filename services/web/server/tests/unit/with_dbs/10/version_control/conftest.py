# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import logging
from copy import deepcopy
from typing import Any, AsyncIterator, Awaitable, Callable, Dict
from uuid import UUID

import aiohttp
import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.projects import ProjectID
from models_library.users import UserID
from pytest_simcore.helpers.rawdata_fakers import random_project
from pytest_simcore.helpers.utils_login import AUserDict
from pytest_simcore.helpers.utils_projects import NewProject
from simcore_postgres_database.models.projects_version_control import (
    projects_vc_repos,
    projects_vc_snapshots,
)
from simcore_service_webserver import catalog
from simcore_service_webserver._meta import API_VTAG as VX
from simcore_service_webserver.db import APP_DB_ENGINE_KEY
from simcore_service_webserver.db_models import UserRole
from simcore_service_webserver.log import setup_logging

ProjectDict = Dict[str, Any]

# HELPERS


# FIXTURES


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
async def catalog_subsystem_mock(monkeypatch, fake_project) -> None:
    services_in_project = [
        {"key": s["key"], "version": s["version"]}
        for _, s in fake_project["workbench"].items()
    ]

    async def mocked_get_services_for_user(*args, **kwargs):
        return services_in_project

    monkeypatch.setattr(
        catalog, "get_services_for_user_in_product", mocked_get_services_for_user
    )


@pytest.fixture
def app_cfg(
    default_app_cfg, aiohttp_unused_port, catalog_subsystem_mock, monkeypatch
) -> Dict[str, Any]:
    """App's configuration used for every test in this module

    NOTE: Overrides services/web/server/tests/unit/with_dbs/conftest.py::app_cfg to influence app setup
    """
    cfg = deepcopy(default_app_cfg)

    monkeypatch.setenv("WEBSERVER_DEV_FEATURES_ENABLED", "1")

    cfg["main"]["port"] = aiohttp_unused_port()
    cfg["main"]["studies_access_enabled"] = True

    exclude = {
        "activity",
        "catalog",
        "clusters",
        "computation",
        "diagnostics",
        "director",
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
    setup_logging(level=logging.DEBUG)

    # Enforces smallest GC in the background task
    cfg["resource_manager"]["garbage_collection_interval_seconds"] = 1

    return cfg


@pytest.fixture
async def user_id(logged_user: AUserDict) -> UserID:
    return logged_user["id"]


@pytest.fixture()
def project_uuid(user_project: ProjectDict) -> ProjectID:
    return UUID(user_project["uuid"])


@pytest.fixture
async def user_project(
    client: TestClient, fake_project: ProjectDict, user_id
) -> AsyncIterator[ProjectDict]:
    # pylint: disable=no-value-for-parameter

    async with NewProject(fake_project, client.app, user_id=user_id) as project:

        yield project

        # cleanup repos
        engine = client.app[APP_DB_ENGINE_KEY]
        async with engine.acquire() as conn:

            # cascade deletes everything except projects_vc_snapshot
            await conn.execute(projects_vc_repos.delete())
            await conn.execute(projects_vc_snapshots.delete())


@pytest.fixture
def do_update_user_project(
    logged_user: AUserDict, client: TestClient, faker: Faker
) -> Callable[[UUID], Awaitable]:
    async def _doit(project_uuid: UUID) -> None:
        resp: aiohttp.ClientResponse = await client.get(f"{VX}/projects/{project_uuid}")

        assert resp.status == 200
        body = await resp.json()
        assert body

        project = body["data"]
        project["workbench"] = {
            faker.uuid4(): {
                "key": f"simcore/services/comp/test_{__name__}",
                "version": "1.0.0",
                "label": f"test_{__name__}",
                "inputs": {"x": faker.pyint(), "y": faker.pyint()},
            }
        }
        resp = await client.put(f"{VX}/projects/{project_uuid}", json=project)
        body = await resp.json()
        assert resp.status == 200, str(body)

    return _doit


@pytest.fixture
def do_delete_user_project(
    logged_user: AUserDict, client: TestClient, mocker
) -> Callable[[UUID], Awaitable]:
    mocker.patch(
        "simcore_service_webserver.projects.projects_api.director_v2_api.delete_pipeline",
    )
    mocker.patch(
        "simcore_service_webserver.projects.projects_api.delete_data_folders_of_project",
    )

    async def _doit(project_uuid: UUID) -> None:

        resp: aiohttp.ClientResponse = await client.delete(
            f"{VX}/projects/{project_uuid}"
        )
        assert resp.status == 204

    return _doit
