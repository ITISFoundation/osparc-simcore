""" helpers to manage the projects's database and produce fixtures/mockup data for testing

"""

# pylint: disable=no-value-for-parameter

import json
import uuid as uuidlib
from http import HTTPStatus
from pathlib import Path
from typing import Any

from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.projects_nodes_io import NodeID
from models_library.services_resources import ServiceResourcesDictHelpers
from simcore_postgres_database.utils_projects_nodes import ProjectNodeCreate
from simcore_service_webserver.projects._db_utils import DB_EXCLUSIVE_COLUMNS
from simcore_service_webserver.projects._groups_db import update_or_insert_project_group
from simcore_service_webserver.projects.db import APP_PROJECT_DBAPI, ProjectDBAPI
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

    new_project = await db.insert_project(
        project_data,
        user_id,
        product_name=product_name,
        force_project_uuid=force_uuid,
        force_as_template=as_template,
        # NOTE: fake initial resources until more is needed
        project_nodes={
            NodeID(node_id): ProjectNodeCreate(
                node_id=NodeID(node_id),
                required_resources=ServiceResourcesDictHelpers.model_config[
                    "json_schema_extra"
                ]["examples"][0],
            )
            for node_id in project_data.get("workbench", {})
        },
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
                new_project["uuid"],
                group_id=int(group_id),
                read=permissions["read"],
                write=permissions["write"],
                delete=permissions["delete"],
            )

    try:
        uuidlib.UUID(str(project_data["uuid"]))
        assert new_project["uuid"] == project_data["uuid"]
    except (ValueError, AssertionError):
        # in that case the uuid gets replaced
        assert new_project["uuid"] != project_data["uuid"]
        project_data["uuid"] = new_project["uuid"]

    for key in DB_EXCLUSIVE_COLUMNS:
        project_data.pop(key, None)

    return new_project


async def delete_all_projects(app: web.Application):
    from simcore_postgres_database.webserver_models import projects

    db = app[APP_PROJECT_DBAPI]
    async with db.engine.acquire() as conn:
        query = projects.delete()
        await conn.execute(query)


class NewProject:
    def __init__(
        self,
        params_override: dict | None = None,
        app: web.Application | None = None,
        *,
        user_id: int,
        product_name: str,
        tests_data_dir: Path,
        force_uuid: bool = False,
        as_template: bool = False,
    ):
        assert app  # nosec

        self.params_override = params_override
        self.user_id = user_id
        self.product_name = product_name
        self.app = app
        self.prj = {}
        self.force_uuid = force_uuid
        self.tests_data_dir = tests_data_dir
        self.as_template = as_template

        assert tests_data_dir.exists()
        assert tests_data_dir.is_dir()

    async def __aenter__(self) -> ProjectDict:
        assert self.app  # nosec

        self.prj = await create_project(
            self.app,
            self.params_override,
            self.user_id,
            product_name=self.product_name,
            force_uuid=self.force_uuid,
            default_project_json=self.tests_data_dir / "fake-project.json",
            as_template=self.as_template,
        )
        return self.prj

    async def __aexit__(self, *args):
        assert self.app  # nosec
        await delete_all_projects(self.app)


async def assert_get_same_project(
    client: TestClient,
    project: ProjectDict,
    expected: HTTPStatus,
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
