""" Implementations of project creation, either cloning other or
from scratch

"""

import logging
from copy import deepcopy
from typing import Any, Dict, Optional, Tuple
from uuid import UUID, uuid4, uuid5

from aiohttp import web
from models_library.basic_types import UUIDStr
from models_library.projects import ProjectID
from models_library.users import UserID

from ..storage_api import copy_data_folders_from_project
from .project_models import ProjectDict, validate_project
from .projects_db import APP_PROJECT_DBAPI, ProjectDBAPI
from .projects_exceptions import ProjectNotFoundError

log = logging.getLogger(__name__)

NodesMap = Dict[UUIDStr, UUIDStr]

AUTO_CREATE_UUID = None


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


def _clone_project_model(
    source_project: ProjectDict,
    *,
    new_project_id: ProjectID,
    clean_output_data: bool = False,
) -> Tuple[ProjectDict, NodesMap]:
    """
    Deep copies a project dataset and modifies:
    - different project ids
    - different node ids
    - w/ or w/o outputs
    """
    #
    # TODO: Not robust to changes in project schema
    #   e.g. how to guarantee these are the outputs?
    #        should we mark these fields?
    #

    cloned_project = deepcopy(source_project)
    cloned_project["uuid"] = f"{new_project_id}"

    # Workbench nodes shall be unique within the project context
    def _create_new_node_uuid(previous_uuid):
        return f"{uuid5(new_project_id, f'{previous_uuid}')}"

    nodes_map: NodesMap = {}
    for node_uuid in source_project.get("workbench", {}).keys():
        nodes_map[node_uuid] = _create_new_node_uuid(node_uuid)

    project_map = {source_project["uuid"]: cloned_project["uuid"]}

    cloned_project["workbench"] = _replace_uuids(
        cloned_project.get("workbench", {}), project_map, nodes_map
    )

    if "ui" in cloned_project:
        cloned_project["ui"]["workbench"] = _replace_uuids(
            cloned_project["ui"].get("workbench", {}), project_map, nodes_map
        )
        cloned_project["ui"]["slideshow"] = _replace_uuids(
            cloned_project["ui"].get("slideshow", {}), project_map, nodes_map
        )
        if "mode" in cloned_project["ui"]:
            cloned_project["ui"]["mode"] = cloned_project["ui"]["mode"]

    if clean_output_data:
        FIELDS_TO_DELETE = ("outputs", "progress", "runHash")
        for node_data in cloned_project.get("workbench", {}).values():
            for field in FIELDS_TO_DELETE:
                node_data.pop(field, None)

    return cloned_project, nodes_map


async def clone_project(
    app: web.Application,
    user_id: UserID,
    source_project_id: ProjectID,
    *,
    copy_data: bool = True,
    as_template: bool = False,
    new_project_id: Optional[UUID] = AUTO_CREATE_UUID,
) -> ProjectDict:
    """
    Let's define clone as a copy with potentially some field
    updates (e.g. new identifiers, etc).

    Clones both project in db and its associated data-folders
    - project
        - get new identifiers for project and nodes
    - data folders
        - folder name composes as project_uuid/node_uuid
        - data is deep-copied to new folder corresponding to new identifiers
        - managed by storage uservice
    """
    # TODO: set as invisible and set visible when copied so it can be used?
    # TODO: atomic operation?

    # TODO: can perform action? check whether user_id can clone project
    # TODO: perform action?

    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]

    # 1 -------------
    # Get source project
    # TODO: use API instead (will verify e.g. access)
    source_project = await db.get_user_project(user_id, f"{source_project_id}")
    if not source_project:
        raise ProjectNotFoundError(source_project_id)

    # 2 -------------
    # Update project id
    new_project_id = new_project_id or uuid4()
    assert isinstance(new_project_id, UUID)  # nosec

    # creates clone
    project_copy, nodes_map = _clone_project_model(
        source_project,
        new_project_id=new_project_id,
        clean_output_data=False,
    )

    # inject in db # TODO: repository pattern
    await validate_project(app, project_copy)
    await db.add_project(
        project_copy, user_id, force_project_uuid=True, force_as_template=True
    )

    # 3 -------------

    if copy_data:
        # TODO: schedule task?
        # TODO: long running https://google.aip.dev/151 ?

        # access writes apply again in
        updated_project = await copy_data_folders_from_project(
            app, source_project, project_copy, nodes_map, user_id
        )

        assert updated_project == project_copy  # nosec

    # 4 -------------
    # update access rights
    if source_project["type"] == "TEMPLATE":
        # remove template access rights
        project_copy["accessRights"] = {}

    return project_copy
