import asyncio
import logging
from collections.abc import Coroutine
from contextlib import AsyncExitStack
from typing import Any, TypeAlias

from aiohttp import web
from common_library.json_serialization import json_dumps
from jsonschema import ValidationError as JsonSchemaValidationError
from models_library.api_schemas_long_running_tasks.base import ProgressPercent
from models_library.api_schemas_webserver.projects import ProjectGet
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID, NodeIDStr
from models_library.projects_state import ProjectStatus
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from models_library.workspaces import UserWorkspaceAccessRightsDB
from pydantic import TypeAdapter
from servicelib.aiohttp.long_running_tasks.server import TaskProgress
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from simcore_postgres_database.utils_projects_nodes import (
    ProjectNode,
    ProjectNodeCreate,
)
from simcore_postgres_database.webserver_models import ProjectType as ProjectTypeDB

from ..application_settings import get_application_settings
from ..catalog import client as catalog_client
from ..director_v2 import api
from ..folders import _folders_db as folders_db
from ..storage.api import (
    copy_data_folders_from_project,
    get_project_total_size_simcore_s3,
)
from ..users.api import get_user_fullname
from ..workspaces import _workspaces_db as workspaces_db
from ..workspaces.api import check_user_workspace_access
from ..workspaces.errors import WorkspaceAccessForbiddenError
from . import _folders_db as project_to_folders_db
from . import projects_api
from ._metadata_api import set_project_ancestors
from ._permalink_api import update_or_pop_permalink_in_project
from .db import ProjectDBAPI
from .exceptions import (
    ParentNodeNotFoundError,
    ParentProjectNotFoundError,
    ProjectInvalidRightsError,
    ProjectNotFoundError,
)
from .models import ProjectDict
from .utils import NodesMap, clone_project_document, default_copy_project_name

OVERRIDABLE_DOCUMENT_KEYS = [
    "name",
    "description",
    "thumbnail",
    "prjOwner",
    "accessRights",
]


log = logging.getLogger(__name__)

CopyFileCoro: TypeAlias = Coroutine[Any, Any, None]
CopyProjectNodesCoro: TypeAlias = Coroutine[Any, Any, dict[NodeID, ProjectNodeCreate]]


async def _prepare_project_copy(
    app: web.Application,
    *,
    user_id: UserID,
    src_project_uuid: ProjectID,
    as_template: bool,
    deep_copy: bool,
    task_progress: TaskProgress,
) -> tuple[ProjectDict, CopyProjectNodesCoro | None, CopyFileCoro | None]:
    source_project = await projects_api.get_project_for_user(
        app,
        project_uuid=f"{src_project_uuid}",
        user_id=user_id,
    )
    settings = get_application_settings(app).WEBSERVER_PROJECTS
    assert settings  # nosec
    if max_bytes := settings.PROJECTS_MAX_COPY_SIZE_BYTES:
        # get project total data size
        project_data_size = await get_project_total_size_simcore_s3(
            app, user_id, src_project_uuid
        )
        if project_data_size >= max_bytes:
            raise web.HTTPUnprocessableEntity(
                reason=f"Source project data size is {project_data_size.human_readable()}."
                f"This is larger than the maximum {max_bytes.human_readable()} allowed for copying."
                "TIP: Please reduce the study size or contact application support."
            )

    # clone template as user project
    new_project, nodes_map = clone_project_document(
        source_project,
        forced_copy_project_id=None,
        clean_output_data=(deep_copy is False),
    )

    # remove template/study access rights
    new_project["accessRights"] = {}
    if not as_template:
        new_project["name"] = default_copy_project_name(source_project["name"])

    copy_project_nodes_coro = None
    if len(nodes_map) > 0:
        copy_project_nodes_coro = _copy_project_nodes_from_source_project(
            app, source_project, nodes_map
        )

    copy_file_coro = None
    if deep_copy and len(nodes_map) > 0:
        copy_file_coro = _copy_files_from_source_project(
            app,
            source_project,
            new_project,
            nodes_map,
            user_id,
            task_progress,
        )
    return new_project, copy_project_nodes_coro, copy_file_coro


async def _copy_project_nodes_from_source_project(
    app: web.Application,
    source_project: ProjectDict,
    nodes_map: NodesMap,
) -> dict[NodeID, ProjectNodeCreate]:
    db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(app)

    def _mapped_node_id(node: ProjectNode) -> NodeID:
        return NodeID(nodes_map[NodeIDStr(f"{node.node_id}")])

    return {
        _mapped_node_id(node): ProjectNodeCreate(
            node_id=_mapped_node_id(node),
            **{
                k: v
                for k, v in node.model_dump().items()
                if k in ProjectNodeCreate.get_field_names(exclude={"node_id"})
            },
        )
        for node in await db.list_project_nodes(ProjectID(source_project["uuid"]))
    }


async def _copy_files_from_source_project(
    app: web.Application,
    source_project: ProjectDict,
    new_project: ProjectDict,
    nodes_map: NodesMap,
    user_id: UserID,
    task_progress: TaskProgress,
):
    db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(app)
    needs_lock_source_project: bool = (
        await db.get_project_type(
            TypeAdapter(ProjectID).validate_python(source_project["uuid"])
        )
        != ProjectTypeDB.TEMPLATE
    )

    async with AsyncExitStack() as stack:
        if needs_lock_source_project:
            await stack.enter_async_context(
                projects_api.lock_with_notification(
                    app,
                    source_project["uuid"],
                    ProjectStatus.CLONING,
                    user_id,
                    await get_user_fullname(app, user_id),
                )
            )
        starting_value = task_progress.percent
        async for long_running_task in copy_data_folders_from_project(
            app, source_project, new_project, nodes_map, user_id
        ):
            task_progress.update(
                message=long_running_task.progress.message,
                percent=TypeAdapter(ProgressPercent).validate_python(
                    (
                        starting_value
                        + long_running_task.progress.percent * (1.0 - starting_value)
                    ),
                ),
            )
            if long_running_task.done():
                await long_running_task.result()


async def _compose_project_data(
    app: web.Application,
    *,
    user_id: UserID,
    new_project: ProjectDict,
    predefined_project: ProjectDict,
) -> tuple[ProjectDict, dict[NodeID, ProjectNodeCreate] | None]:
    project_nodes: dict[NodeID, ProjectNodeCreate] | None = None
    if new_project:  # creates from a copy, just override fields
        # when predefined_project is ProjectCopyOverride
        for key in OVERRIDABLE_DOCUMENT_KEYS:
            if non_null_value := predefined_project.get(key):
                new_project[key] = non_null_value
    else:
        # when predefined_project is ProjectCreateNew
        project_nodes = {
            NodeID(node_id): ProjectNodeCreate(
                node_id=NodeID(node_id),
                required_resources=jsonable_encoder(
                    await catalog_client.get_service_resources(
                        app, user_id, node_data["key"], node_data["version"]
                    )
                ),
            )
            for node_id, node_data in predefined_project.get("workbench", {}).items()
        }

        new_project = predefined_project

    return new_project, project_nodes


async def create_project(  # pylint: disable=too-many-arguments,too-many-branches,too-many-statements  # noqa: C901, PLR0913
    task_progress: TaskProgress,
    *,
    request: web.Request,
    new_project_was_hidden_before_data_was_copied: bool,
    from_study: ProjectID | None,
    as_template: bool,
    copy_data: bool,
    user_id: UserID,
    product_name: str,
    predefined_project: ProjectDict | None,
    simcore_user_agent: str,
    parent_project_uuid: ProjectID | None,
    parent_node_id: NodeID | None,
) -> None:
    """Implements TaskProtocol for 'create_projects' handler

    Arguments:
        task_progress -- TaskProtocol argument
        app
        new_project_was_hidden_before_data_was_copied --
        from_study -- create from an existing study or not (if None)
        as_template -- create as template
        copy_data -- whether s3 data is copied
        user_id
        product_name
        predefined_project -- project in request body

    Raises:
        web.HTTPCreated: succeeded
        web.HTTPBadRequest:
        web.HTTPNotFound:
        web.HTTPUnauthorized:

    """
    assert request.app  # nosec

    db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(request.app)

    new_project: ProjectDict = {}
    copy_file_coro = None
    project_nodes = None
    try:
        task_progress.update(message="creating new study...")

        workspace_id = None
        folder_id = None
        if predefined_project:
            if workspace_id := predefined_project.get("workspaceId", None):
                await check_user_workspace_access(
                    request.app,
                    user_id=user_id,
                    workspace_id=workspace_id,
                    product_name=product_name,
                    permission="write",
                )
            if folder_id := predefined_project.get("folderId", None):
                # Check user has access to folder
                await folders_db.get_for_user_or_workspace(
                    request.app,
                    folder_id=folder_id,
                    product_name=product_name,
                    user_id=user_id if workspace_id is None else None,
                    workspace_id=workspace_id,
                )
                # Folder ID is not part of the project resource
                predefined_project.pop("folderId")

        if from_study:
            # 1.1 prepare copy
            (
                new_project,
                project_node_coro,
                copy_file_coro,
            ) = await _prepare_project_copy(
                request.app,
                user_id=user_id,
                src_project_uuid=from_study,
                as_template=as_template,
                deep_copy=copy_data,
                task_progress=task_progress,
            )
            if project_node_coro:
                project_nodes = await project_node_coro

            # 1.2 does project belong to some folder?
            workspace_id = new_project["workspaceId"]
            prj_to_folder_db = await project_to_folders_db.get_project_to_folder(
                request.app,
                project_id=from_study,
                private_workspace_user_id_or_none=(
                    user_id if workspace_id is None else None
                ),
            )
            if prj_to_folder_db:
                # As user has access to the project, it has implicitly access to the folder
                folder_id = prj_to_folder_db.folder_id

            if as_template:
                # For template we do not care about workspace/folder
                workspace_id = None
                new_project["workspaceId"] = workspace_id
                folder_id = None

        if predefined_project:
            # 2. overrides with optional body and re-validate
            new_project, project_nodes = await _compose_project_data(
                request.app,
                user_id=user_id,
                new_project=new_project,
                predefined_project=predefined_project,
            )

        # 3.1 save new project in DB
        new_project = await db.insert_project(
            project=jsonable_encoder(new_project),
            user_id=user_id,
            product_name=product_name,
            force_as_template=as_template,
            hidden=copy_data,
            project_nodes=project_nodes,
        )
        # add parent linking if needed
        await set_project_ancestors(
            request.app,
            user_id=user_id,
            project_uuid=new_project["uuid"],
            parent_project_uuid=parent_project_uuid,
            parent_node_id=parent_node_id,
        )
        task_progress.update()

        # 3.2 move project to proper folder
        if folder_id:
            await project_to_folders_db.insert_project_to_folder(
                request.app,
                project_id=new_project["uuid"],
                folder_id=folder_id,
                private_workspace_user_id_or_none=(
                    user_id if workspace_id is None else None
                ),
            )

        # 4. deep copy source project's files
        if copy_file_coro:
            # NOTE: storage needs to have access to the new project prior to copying files
            await copy_file_coro

        # 5. unhide the project if needed since it is now complete
        if not new_project_was_hidden_before_data_was_copied:
            await db.set_hidden_flag(new_project["uuid"], hidden=False)

        # update the network information in director-v2
        await api.update_dynamic_service_networks_in_project(
            request.app, ProjectID(new_project["uuid"])
        )
        task_progress.update()

        # This is a new project and every new graph needs to be reflected in the pipeline tables
        await api.create_or_update_pipeline(
            request.app, user_id, new_project["uuid"], product_name
        )
        # get the latest state of the project (lastChangeDate for instance)
        new_project, _ = await db.get_project(project_uuid=new_project["uuid"])
        # Appends state
        new_project = await projects_api.add_project_states_for_user(
            user_id=user_id,
            project=new_project,
            is_template=as_template,
            app=request.app,
        )
        task_progress.update()

        # Adds permalink
        await update_or_pop_permalink_in_project(request, new_project)

        # Adds folderId
        user_specific_project_data_db = await db.get_user_specific_project_data_db(
            project_uuid=new_project["uuid"],
            private_workspace_user_id_or_none=user_id if workspace_id is None else None,
        )
        new_project["folderId"] = user_specific_project_data_db.folder_id

        # Overwrite project access rights
        if workspace_id:
            workspace_db: UserWorkspaceAccessRightsDB = (
                await workspaces_db.get_workspace_for_user(
                    app=request.app,
                    user_id=user_id,
                    workspace_id=workspace_id,
                    product_name=product_name,
                )
            )
            new_project["accessRights"] = {
                f"{gid}": access.model_dump()
                for gid, access in workspace_db.access_rights.items()
            }

        # Ensures is like ProjectGet
        data = ProjectGet.model_validate(new_project).data(exclude_unset=True)

        raise web.HTTPCreated(
            text=json_dumps({"data": data}),
            content_type=MIMETYPE_APPLICATION_JSON,
        )

    except JsonSchemaValidationError as exc:
        raise web.HTTPBadRequest(reason="Invalid project data") from exc

    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"Project {exc.project_uuid} not found") from exc

    except (ProjectInvalidRightsError, WorkspaceAccessForbiddenError) as exc:
        raise web.HTTPForbidden from exc

    except (ParentProjectNotFoundError, ParentNodeNotFoundError) as exc:
        if project_uuid := new_project.get("uuid"):
            await projects_api.submit_delete_project_task(
                app=request.app,
                project_uuid=project_uuid,
                user_id=user_id,
                simcore_user_agent=simcore_user_agent,
            )
        raise web.HTTPNotFound(reason=f"{exc}") from exc

    except asyncio.CancelledError:
        log.warning(
            "cancelled create_project for '%s'. Cleaning up",
            f"{user_id=}",
        )
        if project_uuid := new_project.get("uuid"):
            await projects_api.submit_delete_project_task(
                app=request.app,
                project_uuid=project_uuid,
                user_id=user_id,
                simcore_user_agent=simcore_user_agent,
            )
        raise
