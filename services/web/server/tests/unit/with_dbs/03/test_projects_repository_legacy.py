# pylint: disable=no-value-for-parameter
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

"""Tests to reproduce and verify fixes for asyncpg migration bugs
in _projects_repository_legacy.py and _projects_repository_legacy_utils.py.

Each test targets a specific bug found during the aiopg→asyncpg conversion:
- Bug 1: list_projects_uuids — Row access by SA column object
- Bug 2: get_project_type — Row access by SA column object
- Bug 3: list_projects_dicts — enum .value string vs sa.Enum column filter
- Bug 4: published_project_read_condition — enum .value comparison
- Bug 5: insert_project — enum .value in INSERT values
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from copy import deepcopy
from typing import Any

import pytest
from aiohttp.test_utils import TestClient
from models_library.folders import FolderQuery, FolderScope
from models_library.projects import ProjectID
from models_library.workspaces import WorkspaceQuery, WorkspaceScope
from simcore_postgres_database.models.projects import ProjectType, projects
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.projects._groups_repository import (
    update_or_insert_project_group,
)
from simcore_service_webserver.projects._projects_repository_legacy import (
    ProjectDBAPI,
)
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture()
def db_api(
    client: TestClient,
) -> ProjectDBAPI:
    assert client.app
    return ProjectDBAPI.get_from_app_context(app=client.app)


@pytest.fixture
async def insert_project_in_db(
    asyncpg_engine: AsyncEngine,
    db_api: ProjectDBAPI,
    osparc_product_name: str,
    client: TestClient,
) -> AsyncIterator[Callable[..., Awaitable[dict[str, Any]]]]:
    inserted_projects: list[str] = []
    assert client.app

    async def _inserter(prj: dict[str, Any], **overrides) -> dict[str, Any]:
        default_config: dict[str, Any] = {
            "project": prj,
            "user_id": None,
            "product_name": osparc_product_name,
            "project_nodes": None,
        }
        default_config.update(**overrides)
        new_project = await db_api.insert_project(**default_config)
        if _access_rights := default_config["project"].get("access_rights", {}) | default_config["project"].get(
            "accessRights", {}
        ):
            for group_id, permissions in _access_rights.items():
                await update_or_insert_project_group(
                    client.app,
                    project_id=new_project["uuid"],
                    group_id=int(group_id),
                    read=permissions["read"],
                    write=permissions["write"],
                    delete=permissions["delete"],
                )
        inserted_projects.append(new_project["uuid"])
        return new_project

    yield _inserter

    # Cleanup inserted projects
    async with asyncpg_engine.begin() as conn:
        await conn.execute(projects.delete().where(projects.c.uuid.in_(inserted_projects)))


async def test_insert_project_bug5(
    db_api: ProjectDBAPI,
    fake_project: dict[str, Any],
    osparc_product_name: str,
):
    """Bug 5: insert_project passes enum .value strings to sa.Enum columns.
    asyncpg rejects string values for enum-typed columns.
    """
    new_project = await db_api.insert_project(
        project=deepcopy(fake_project),
        user_id=None,
        product_name=osparc_product_name,
        project_nodes=None,
    )
    assert new_project
    assert new_project["uuid"]


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_list_projects_uuids_bug1(
    logged_user: dict[str, Any],
    db_api: ProjectDBAPI,
    insert_project_in_db: Callable[..., Awaitable[dict[str, Any]]],
    fake_project: dict[str, Any],
):
    """Bug 1: list_projects_uuids uses row[projects.c.uuid] subscript on asyncpg Row.
    asyncpg Row does not support SA column object as subscript key.
    """
    project = await insert_project_in_db(deepcopy(fake_project), user_id=logged_user["id"])
    result = await db_api.list_projects_uuids(logged_user["id"])
    assert project["uuid"] in result


async def test_get_project_type_bug2(
    db_api: ProjectDBAPI,
    insert_project_in_db: Callable[..., Awaitable[dict[str, Any]]],
    fake_project: dict[str, Any],
):
    """Bug 2: get_project_type uses row[projects.c.type] subscript on asyncpg Row.
    asyncpg Row does not support SA column object as subscript key.
    """
    project = await insert_project_in_db(deepcopy(fake_project))
    project_uuid = ProjectID(project["uuid"])
    project_type = await db_api.get_project_type(project_uuid)
    assert project_type == ProjectType.TEMPLATE


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_list_projects_dicts_filter_by_type_bug3(
    logged_user: dict[str, Any],
    db_api: ProjectDBAPI,
    insert_project_in_db: Callable[..., Awaitable[dict[str, Any]]],
    fake_project: dict[str, Any],
    osparc_product_name: str,
):
    """Bug 3: _create_attributes_filters passes enum .value string to sa.Enum column.
    asyncpg rejects comparing enum column with plain string.
    """
    project = await insert_project_in_db(deepcopy(fake_project), user_id=logged_user["id"], force_as_template=True)
    result, total = await db_api.list_projects_dicts(
        product_name=osparc_product_name,
        user_id=logged_user["id"],
        workspace_query=WorkspaceQuery(
            workspace_scope=WorkspaceScope.PRIVATE,
            workspace_id=None,
        ),
        folder_query=FolderQuery(
            folder_scope=FolderScope.ROOT,
            folder_id=None,
        ),
        filter_by_project_type=ProjectType.TEMPLATE,
        filter_trashed=False,
        filter_hidden=False,
    )
    assert total > 0, "Expected to find the inserted template project"
    assert any(p["uuid"] == project["uuid"] for p in result)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_get_project_dict_and_type_only_templates_bug4(
    logged_user: dict[str, Any],
    db_api: ProjectDBAPI,
    insert_project_in_db: Callable[..., Awaitable[dict[str, Any]]],
    fake_project: dict[str, Any],
    asyncpg_engine: AsyncEngine,
):
    """Bug 4: published_project_read_condition compares enum column with .value string.
    Reproduces via get_project_dict_and_type with only_templates=True, only_published=True.
    """
    # Insert as template (no user_id)
    project = await insert_project_in_db(deepcopy(fake_project))
    # Mark as published
    async with asyncpg_engine.begin() as conn:
        await conn.execute(projects.update().where(projects.c.uuid == project["uuid"]).values(published=True))
    project_dict, project_type = await db_api.get_project_dict_and_type(
        project["uuid"],
        only_templates=True,
        only_published=True,
    )
    assert project_type == ProjectType.TEMPLATE
    assert project_dict["uuid"] == project["uuid"]
