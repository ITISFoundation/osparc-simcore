""" helpers to manage the projects's database and produce fixtures/mockup data for testing

"""
# pylint: disable=no-value-for-parameter

import json
import re
import uuid as uuidlib
from copy import deepcopy
from typing import Any, Dict, Tuple

from aiohttp import web
from simcore_service_webserver.projects.projects_db import (
    APP_PROJECT_DBAPI,
    DB_EXCLUSIVE_COLUMNS,
)
from simcore_service_webserver.resources import resources
from simcore_service_webserver.utils import now_str

fake_template_resources = [
    "data/" + name
    for name in resources.listdir("data")
    if re.match(r"^fake-template-(.+).json", name)
]

fake_project_resources = [
    "data/" + name
    for name in resources.listdir("data")
    if re.match(r"^fake-user-(.+).json", name)
]


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


def load_data(name):
    with resources.stream(name) as fp:
        return json.load(fp)


async def create_project(
    app: web.Application, params: Dict = None, user_id=None, *, force_uuid=False
) -> Dict:
    """Injects new project in database for user or as template

    :param params: predefined project properties (except for non-writeable e.g. uuid), defaults to None
    :type params: Dict, optional
    :param user_id: assigns this project to user or template project if None, defaults to None
    :type user_id: int, optional
    :return: schema-compliant project
    :rtype: Dict
    """
    params = params or {}

    project_data = load_data("data/fake-template-projects.isan.json")[0]
    project_data.update(params)

    db = app[APP_PROJECT_DBAPI]

    new_project = await db.add_project(
        project_data, user_id, force_project_uuid=force_uuid
    )
    try:
        uuidlib.UUID(project_data["uuid"])
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


def clone_project_data(project: Dict[str, Any]) -> Tuple[Dict, Dict]:
    project_copy = deepcopy(project)

    # Update project id
    # NOTE: this can be re-assigned by dbapi if not unique
    project_copy_uuid = uuidlib.uuid1()  # random project id
    project_copy["uuid"] = str(project_copy_uuid)

    # Workbench nodes shall be unique within the project context
    def _create_new_node_uuid(old_uuid):
        return str(uuidlib.uuid5(project_copy_uuid, str(old_uuid)))

    nodes_map = {}
    for node_uuid in project.get("workbench", {}).keys():
        nodes_map[node_uuid] = _create_new_node_uuid(node_uuid)

    def _replace_uuids(node):
        if isinstance(node, str):
            node = nodes_map.get(node, node)
        elif isinstance(node, list):
            node = [_replace_uuids(item) for item in node]
        elif isinstance(node, dict):
            _frozen_items = tuple(node.items())
            for key, value in _frozen_items:
                if key in nodes_map:
                    new_key = nodes_map[key]
                    node[new_key] = node.pop(key)
                    key = new_key
                node[key] = _replace_uuids(value)
        return node

    project_copy["workbench"] = _replace_uuids(project_copy.get("workbench", {}))
    return project_copy, nodes_map


class NewProject:
    def __init__(
        self,
        params: Dict = None,
        app: web.Application = None,
        clear_all=True,
        user_id=None,
        *,
        force_uuid=False,
    ):
        self.params = params
        self.user_id = user_id
        self.app = app
        self.prj = {}
        self.clear_all = clear_all
        self.force_uuid = force_uuid

        if not self.clear_all:
            # TODO: add delete_project. Deleting a single project implies having to delete as well all dependencies created
            raise ValueError(
                "UNDER DEVELOPMENT: Currently can only delete all projects "
            )

    async def __aenter__(self):
        self.prj = await create_project(
            self.app, self.params, self.user_id, force_uuid=self.force_uuid
        )
        return self.prj

    async def __aexit__(self, *args):
        if self.clear_all:
            await delete_all_projects(self.app)
