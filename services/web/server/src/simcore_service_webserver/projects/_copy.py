""" Implementation of project copy operations


"""

import logging
from copy import deepcopy
from typing import Dict, List, Optional, Tuple, Union
from uuid import UUID, uuid1, uuid5

from aiohttp import web

from ..storage_api import copy_data_folders_from_project

log = logging.getLogger(__name__)


def clone_project_document(
    project: Dict,
    *,
    forced_copy_project_id: Optional[UUID] = None,
    clean_output_data: bool = False,
) -> Tuple[Dict, Dict]:
    project_copy = deepcopy(project)

    # Update project id
    # NOTE: this can be re-assigned by dbapi if not unique
    if forced_copy_project_id:
        assert isinstance(forced_copy_project_id, UUID)  # nosec
        project_copy_uuid = forced_copy_project_id
    else:
        project_copy_uuid = uuid1()  # random project id

    assert project_copy_uuid  # nosec

    project_copy["uuid"] = str(project_copy_uuid)

    # Workbench nodes shall be unique within the project context
    def _create_new_node_uuid(old_uuid):
        return str(uuid5(project_copy_uuid, str(old_uuid)))

    nodes_map = {}
    for node_uuid in project.get("workbench", {}).keys():
        nodes_map[node_uuid] = _create_new_node_uuid(node_uuid)

    project_map = {project["uuid"]: project_copy["uuid"]}

    def _replace_uuids(node: Union[str, List, Dict]) -> Union[str, List, Dict]:
        if isinstance(node, str):
            # NOTE: for datasets we get something like project_uuid/node_uuid/file_id
            if "/" in node:
                parts = node.split("/")
                node = "/".join(_replace_uuids(part) for part in parts)
            else:
                node = project_map.get(node, nodes_map.get(node, node))
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
    if "ui" in project_copy:
        project_copy["ui"]["workbench"] = _replace_uuids(
            project_copy["ui"].get("workbench", {})
        )
        project_copy["ui"]["slideshow"] = _replace_uuids(
            project_copy["ui"].get("slideshow", {})
        )
        if "mode" in project_copy["ui"]:
            project_copy["ui"]["mode"] = project_copy["ui"]["mode"]
    if clean_output_data:
        FIELDS_TO_DELETE = ("outputs", "progress", "runHash")
        for node_data in project_copy.get("workbench", {}).values():
            for field in FIELDS_TO_DELETE:
                node_data.pop(field, None)
    return project_copy, nodes_map


async def clone_project(
    app: web.Application, project: Dict, user_id: int, forced_copy_project_id: str = ""
) -> Dict:
    """Clones both document and data folders of a project

    - document
        - get new identifiers for project and nodes
    - data folders
        - folder name composes as project_uuid/node_uuid
        - data is deep-copied to new folder corresponding to new identifiers
        - managed by storage uservice
    """

    #
    # NOTE: Needs refactoring after access-layer in storage. DO NOT USE but keep
    #      here since it documents well the concept

    cloned_project, nodes_map = clone_project_document(project, forced_copy_project_id)

    updated_project = await copy_data_folders_from_project(
        app, project, cloned_project, nodes_map, user_id
    )

    return updated_project
