# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import logging
from copy import deepcopy
from typing import Any, Dict, Iterator

import pytest
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.rawdata_fakers import random_project
from pytest_simcore.helpers.utils_login import UserDict
from pytest_simcore.helpers.utils_projects import NewProject
from simcore_postgres_database.models.projects_version_control import (
    projects_vc_repos,
    projects_vc_snapshots,
)
from simcore_service_webserver import catalog
from simcore_service_webserver.db import APP_DB_ENGINE_KEY
from simcore_service_webserver.db_models import UserRole
from simcore_service_webserver.log import setup_logging

ProjectDict = Dict[str, Any]


@pytest.fixture
def user_role() -> UserRole:
    return UserRole.USER


@pytest.fixture
def fake_project() -> ProjectDict:
    # API model project data
    return random_project(name=f"{__file__}-project")


@pytest.fixture
async def catalog_subsystem_mock(monkeypatch, fake_project):
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
def app_cfg(default_app_cfg, aiohttp_unused_port, catalog_subsystem_mock, monkeypatch):
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
        "resource_manager",
        "smtp",
        "socketio",
        "storage",
        "studies_access",
        "studies_dispatcher",
        "tags",
        "tracing",
    }
    include = {
        "db",
        "login",
        "products",
        "projects",
        "meta",
        "rest",
        "users",
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
async def user_id(logged_user: UserDict) -> int:
    return logged_user["id"]


@pytest.fixture
async def user_project(
    client: TestClient, fake_project: ProjectDict, user_id
) -> Iterator[ProjectDict]:
    async with NewProject(fake_project, client.app, user_id=user_id) as project:

        yield project

        # cleanup repos
        engine = client.app[APP_DB_ENGINE_KEY]
        async with engine.acquire() as conn:
            # pylint: disable=no-value-for-parameter

            # cascade deletes everything except projects_vc_snapshot
            await conn.execute(projects_vc_repos.delete())
            await conn.execute(projects_vc_snapshots.delete())
