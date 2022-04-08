""" Implementations of project creations

"""

import logging
from copy import deepcopy
from typing import Any, Dict, Optional, Tuple
from uuid import UUID, uuid1, uuid5

from aiohttp import web
from models_library.basic_types import UUIDStr
from models_library.users import UserID

from ..storage_api import copy_data_folders_from_project
from .project_models import ProjectDict
from .projects_db import APP_PROJECT_DBAPI, ProjectDBAPI

log = logging.getLogger(__name__)

NodesMap = Dict[UUIDStr, UUIDStr]


def _replace_uuids(entity: Any, project_map, nodes_map) -> Any:

    if isinstance(entity, str):
        # NOTE: for datasets we get something like project_uuid/node_uuid/file_id
        if "/" in entity:
            parts = entity.split("/")
            entity = "/".join(
                _replace_uuids(part, project_map, nodes_map) for part in parts
            )
        else:
            entity = project_map.get(entity, nodes_map.get(entity, entity))
    elif isinstance(entity, list):
        entity = [_replace_uuids(item, project_map, nodes_map) for item in entity]

    elif isinstance(entity, dict):
        _frozen_items = tuple(entity.items())
        for key, value in _frozen_items:
            if key in nodes_map:
                new_key = nodes_map[key]
                entity[new_key] = entity.pop(key)
                key = new_key

            entity[key] = _replace_uuids(value, project_map, nodes_map)
    return entity


def _clone_project_from(
    project: ProjectDict,
    *,
    new_project_id: Optional[UUID],
    clean_output_data: bool = False,
) -> Tuple[ProjectDict, NodesMap]:
    """
    Deep copies a project dataset and modifies:
    - different project ids
    - different node ids
    - w/ or w/o outputs
    """
    #
    # TODO: not robust to changes in project schema
    #

    project_copy = deepcopy(project)

    # Update project id
    # NOTE: this can be re-assigned by dbapi if not unique
    if new_project_id:
        assert isinstance(new_project_id, UUID)  # nosec
        project_copy_uuid = new_project_id
    else:
        project_copy_uuid = uuid1()  # random project id

    project_copy["uuid"] = str(project_copy_uuid)

    # Workbench nodes shall be unique within the project context
    def _create_new_node_uuid(old_uuid):
        return str(uuid5(project_copy_uuid, str(old_uuid)))

    nodes_map = {}
    for node_uuid in project.get("workbench", {}).keys():
        nodes_map[node_uuid] = _create_new_node_uuid(node_uuid)

    project_map = {project["uuid"]: project_copy["uuid"]}

    project_copy["workbench"] = _replace_uuids(
        project_copy.get("workbench", {}), project_map, nodes_map
    )
    if "ui" in project_copy:
        project_copy["ui"]["workbench"] = _replace_uuids(
            project_copy["ui"].get("workbench", {}), project_map, nodes_map
        )
        project_copy["ui"]["slideshow"] = _replace_uuids(
            project_copy["ui"].get("slideshow", {}), project_map, nodes_map
        )
        if "mode" in project_copy["ui"]:
            project_copy["ui"]["mode"] = project_copy["ui"]["mode"]

    if clean_output_data:
        FIELDS_TO_DELETE = ("outputs", "progress", "runHash")
        for node_data in project_copy.get("workbench", {}).values():
            for field in FIELDS_TO_DELETE:
                node_data.pop(field, None)

    return project_copy, nodes_map


async def copy_project(
    app: web.Application,
    project: ProjectDict,
    user_id: UserID,
    new_project_id: Optional[UUID] = None,
) -> ProjectDict:
    """Clones both document and data folders of a project

    - document
        - get new identifiers for project and nodes
    - data folders
        - folder name composes as project_uuid/node_uuid
        - data is deep-copied to new folder corresponding to new identifiers
        - managed by storage uservice
    """
    # TODO: set as invisible and set visible when copied so it can be used?
    # TODO: atomic operation?

    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]

    # creates clone
    project_copy, nodes_map = _clone_project_from(
        project,
        new_project_id=new_project_id,
        clean_output_data=False,
    )

    # inject in db
    await db.add_project(project_copy, user_id, force_project_uuid=True)

    # access writes apply again in
    updated_project = await copy_data_folders_from_project(
        app, project, project_copy, nodes_map, user_id
    )

    assert updated_project == project_copy  # nosec

    return updated_project


# def create_project( source_project: ProjectID, )
