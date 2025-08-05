"""helpers to manage the projects's database and produce fixtures/mockup data for testing"""

# pylint: disable=no-value-for-parameter

import json
import uuid as uuidlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from aiohttp import web
from aiohttp.test_utils import TestClient
from common_library.dict_tools import remap_keys
from models_library.projects_nodes_io import NodeID
from models_library.services_resources import ServiceResourcesDictHelpers
from simcore_postgres_database.utils_projects_nodes import ProjectNodeCreate
from simcore_service_webserver.projects._groups_repository import (
    update_or_insert_project_group,
)
from simcore_service_webserver.projects._projects_repository_legacy import (
    APP_PROJECT_DBAPI,
    ProjectDBAPI,
)
from simcore_service_webserver.projects._projects_repository_legacy_utils import (
    DB_EXCLUSIVE_COLUMNS,
)
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.utils import now_str

from .assert_checks import assert_status


def empty_project_data():
    return {
        "uuid": f"project-{uuidlib.uuid4()}",
        "name": "Empty name",
        "description": "some description of an empty project",
        "prjOwner": "I'm the empty project owner, hi!",
        "creationDate": now_str(),
        "lastChangeDate": now_str(),
        "thumbnail": "",
        "workbench": {},
    }


async def create_project(
    app: web.Application,
    params_override: dict[str, Any] | None = None,
    user_id: int | None = None,
    *,
    product_name: str,
    default_project_json: Path | None = None,
    force_uuid: bool = False,
    as_template: bool = False,
) -> ProjectDict:
    """Injects new project in database for user or as template

    :param params_override: predefined project properties (except for non-writeable e.g. uuid), defaults to None
    :type params_override: Dict, optional
    :param user_id: assigns this project to user or template project if None, defaults to None
    :type user_id: int, optional
    :return: schema-compliant project
    :rtype: Dict
    """
    params_override = params_override or {}

    project_data = {}
    if default_project_json is not None:
        # uses default_project_json as base
        assert default_project_json.exists(), f"{default_project_json}"
        project_data = json.loads(default_project_json.read_text())

    project_data.update(params_override)

    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]

    raw_workbench: dict[str, Any] = project_data.pop("workbench", {})
    for raw_node in raw_workbench.values():
        if "position" in raw_node:
            del raw_node["position"]

    # Get valid ProjectNodeCreate fields, excluding node_id since it's set separately
    valid_fields = ProjectNodeCreate.get_field_names(exclude={"node_id"})

    # Mapping from camelCase (workbench) to snake_case (ProjectNodeCreate)
    field_mapping = {
        "inputAccess": "input_access",
        "inputNodes": "input_nodes",
        "inputsUnits": "inputs_units",
        "outputNodes": "output_nodes",
        "runHash": "run_hash",
        "bootOptions": "boot_options",
    }

    fake_required_resources: dict[str, Any] = ServiceResourcesDictHelpers.model_config[
        "json_schema_extra"
    ]["examples"][0]

    project_nodes = {
        NodeID(node_id): ProjectNodeCreate(
            node_id=NodeID(node_id),
            # NOTE: fake initial resources until more is needed
            required_resources=fake_required_resources,
            **{
                str(field_mapping.get(field, field)): value
                for field, value in raw_node.items()
                if field_mapping.get(field, field) in valid_fields
            },
        )
        for node_id, raw_node in raw_workbench.items()
    }

    project_created = await db.insert_project(
        project_data,
        user_id,
        product_name=product_name,
        force_project_uuid=force_uuid,
        force_as_template=as_template,
        project_nodes=project_nodes,
    )

    if params_override and (
        params_override.get("access_rights") or params_override.get("accessRights")
    ):
        _access_rights = params_override.get("access_rights", {}) | params_override.get(
            "accessRights", {}
        )
        for group_id, permissions in _access_rights.items():
            await update_or_insert_project_group(
                app,
                project_id=project_created["uuid"],
                group_id=int(group_id),
                read=permissions["read"],
                write=permissions["write"],
                delete=permissions["delete"],
            )

    try:
        uuidlib.UUID(str(project_data["uuid"]))
        assert project_created["uuid"] == project_data["uuid"]
    except (ValueError, AssertionError):
        # in that case the uuid gets replaced
        assert project_created["uuid"] != project_data["uuid"]
        project_data["uuid"] = project_created["uuid"]

    for key in DB_EXCLUSIVE_COLUMNS:
        project_data.pop(key, None)

    project_created: ProjectDict = remap_keys(
        project_created,
        rename={"trashed": "trashedAt"},
    )
    project_created["workbench"] = raw_workbench
    return project_created


async def delete_all_projects(app: web.Application):
    from simcore_postgres_database.webserver_models import projects

    db = app[APP_PROJECT_DBAPI]
    async with db.engine.acquire() as conn:
        query = projects.delete()
        await conn.execute(query)


@asynccontextmanager
async def new_project(
    params_override: dict | None = None,
    app: web.Application | None = None,
    *,
    user_id: int,
    product_name: str,
    tests_data_dir: Path,
    force_uuid: bool = False,
    as_template: bool = False,
) -> AsyncIterator[ProjectDict]:
    assert app  # nosec
    assert tests_data_dir.exists()
    assert tests_data_dir.is_dir()

    project = await create_project(
        app,
        params_override,
        user_id,
        product_name=product_name,
        force_uuid=force_uuid,
        default_project_json=tests_data_dir / "fake-project.json",
        as_template=as_template,
    )

    try:
        yield project
    finally:
        await delete_all_projects(app)


async def assert_get_same_project(
    client: TestClient,
    project: ProjectDict,
    expected: int,
    api_vtag="/v0",
) -> dict:
    # GET /v0/projects/{project_id}

    # with a project owned by user
    assert client.app
    url = client.app.router["get_project"].url_for(project_id=project["uuid"])
    assert str(url) == f"{api_vtag}/projects/{project['uuid']}"
    resp = await client.get(f"{url}")
    data, error = await assert_status(resp, expected)

    if not error:
        assert data == {k: project[k] for k in data}
    return data
