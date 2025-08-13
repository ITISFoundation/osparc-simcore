import asyncio
import logging
from collections.abc import Coroutine
from typing import Any, TypeAlias

from aiohttp import web
from common_library.json_serialization import json_dumps
from jsonschema import ValidationError as JsonSchemaValidationError
from models_library.api_schemas_long_running_tasks.base import ProgressPercent
from models_library.api_schemas_webserver.projects import ProjectGet
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_access import Owner
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import ProjectStatus
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from models_library.workspaces import UserWorkspaceWithAccessRights
from pydantic import TypeAdapter
from servicelib.long_running_tasks.models import TaskProgress
from servicelib.long_running_tasks.task import TaskRegistry
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.redis import with_project_locked
from servicelib.rest_constants import RESPONSE_MODEL_POLICY
from simcore_postgres_database.utils_projects_nodes import (
    ProjectNode,
    ProjectNodeCreate,
)
from simcore_postgres_database.webserver_models import ProjectType as ProjectTypeDB
from yarl import URL

from ..application_settings import get_application_settings
from ..catalog import catalog_service
from ..director_v2 import director_v2_service
from ..dynamic_scheduler import api as dynamic_scheduler_service
from ..folders import _folders_repository as folders_folders_repository
from ..redis import get_redis_lock_manager_client_sdk
from ..storage.api import (
    copy_data_folders_from_project,
    get_project_total_size_simcore_s3,
)
from ..workspaces.api import check_user_workspace_access, get_user_workspace
from ..workspaces.errors import WorkspaceAccessForbiddenError
from . import _folders_repository, _projects_repository, _projects_service
from ._metadata_service import set_project_ancestors
from ._permalink_service import update_or_pop_permalink_in_project
from ._projects_repository_legacy import ProjectDBAPI
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


_logger = logging.getLogger(__name__)

CopyFileCoro: TypeAlias = Coroutine[Any, Any, None]
CopyProjectNodesCoro: TypeAlias = Coroutine[Any, Any, dict[NodeID, ProjectNodeCreate]]


async def _prepare_project_copy(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    src_project_uuid: ProjectID,
    as_template: bool,
    deep_copy: bool,
    task_progress: TaskProgress,
) -> tuple[ProjectDict, CopyProjectNodesCoro | None, CopyFileCoro | None]:
    source_project = await _projects_service.get_project_for_user(
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
                text=f"Source project data size is {project_data_size.human_readable()}."
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
            product_name,
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
        return NodeID(nodes_map[f"{node.node_id}"])

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
    product_name: str,
    task_progress: TaskProgress,
):
    _projects_repository_legacy = ProjectDBAPI.get_from_app_context(app)

    needs_lock_source_project: bool = (
        await _projects_repository_legacy.get_project_type(
            TypeAdapter(ProjectID).validate_python(source_project["uuid"])
        )
        != ProjectTypeDB.TEMPLATE
    )

    async def _copy() -> None:
        starting_value = task_progress.percent
        async for async_job_composed_result in copy_data_folders_from_project(
            app,
            source_project=source_project,
            destination_project=new_project,
            nodes_map=nodes_map,
            user_id=user_id,
            product_name=product_name,
        ):
            await task_progress.update(
                message=(
                    async_job_composed_result.status.progress.message.description
                    if async_job_composed_result.status.progress.message
                    else None
                ),
                percent=TypeAdapter(ProgressPercent).validate_python(
                    (
                        starting_value
                        + async_job_composed_result.status.progress.percent_value
                        * (1.0 - starting_value)
                    ),
                ),
            )
            if async_job_composed_result.done:
                await async_job_composed_result.result()

    if needs_lock_source_project:
        await with_project_locked(
            get_redis_lock_manager_client_sdk(app),
            project_uuid=source_project["uuid"],
            status=ProjectStatus.CLONING,
            owner=Owner(user_id=user_id),
            notification_cb=_projects_service.create_user_notification_cb(
                user_id, ProjectID(f"{source_project['uuid']}"), app
            ),
        )(_copy)()
    else:
        await _copy()


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
                    await catalog_service.get_service_resources(
                        app, user_id, node_data["key"], node_data["version"]
                    )
                ),
                key=node_data.get("key"),
                version=node_data.get("version"),
                label=node_data.get("label"),
            )
            for node_id, node_data in predefined_project.get("workbench", {}).items()
        }

        new_project = predefined_project

    return new_project, project_nodes


async def create_project(  # pylint: disable=too-many-arguments,too-many-branches,too-many-statements  # noqa: C901, PLR0913
    progress: TaskProgress,
    *,
    app: web.Application,
    url: URL,
    headers: dict[str, str],
    new_project_was_hidden_before_data_was_copied: bool,
    from_study: ProjectID | None,
    as_template: bool,
    copy_data: bool,
    user_id: UserID,
    product_name: str,
    product_api_base_url: str,
    predefined_project: ProjectDict | None,
    simcore_user_agent: str,
    parent_project_uuid: ProjectID | None,
    parent_node_id: NodeID | None,
) -> web.HTTPCreated:
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
        web.HTTPBadRequest:
        web.HTTPNotFound:
        web.HTTPUnauthorized:

    """
    _logger.info(
        "create_project for '%s' with %s %s %s",
        f"{user_id=}",
        f"{predefined_project=}",
        f"{product_name=}",
        f"{from_study=}",
    )

    _projects_repository_legacy = ProjectDBAPI.get_from_app_context(app)

    new_project: ProjectDict = {}
    copy_file_coro = None
    project_nodes = None
    try:
        await progress.update(message="creating new study...")

        workspace_id = None
        folder_id = None
        if predefined_project:
            if workspace_id := predefined_project.get("workspaceId", None):
                await check_user_workspace_access(
                    app,
                    user_id=user_id,
                    workspace_id=workspace_id,
                    product_name=product_name,
                    permission="write",
                )
            if folder_id := predefined_project.get("folderId", None):
                # Check user has access to folder
                await folders_folders_repository.get_for_user_or_workspace(
                    app,
                    folder_id=folder_id,
                    product_name=product_name,
                    user_id=user_id if workspace_id is None else None,
                    workspace_id=workspace_id,
                )
                # Folder ID is not part of the project resource
                predefined_project.pop("folderId")

        if from_study:  # Either clone or creation of template out of study
            # 1.1 prepare copy
            (
                new_project,
                project_node_coro,
                copy_file_coro,
            ) = await _prepare_project_copy(
                app,
                user_id=user_id,
                product_name=product_name,
                src_project_uuid=from_study,
                as_template=as_template,
                deep_copy=copy_data,
                task_progress=progress,
            )
            if project_node_coro:
                project_nodes = await project_node_coro

            # 1.2 does project belong to some folder?
            workspace_id = new_project["workspaceId"]
            prj_to_folder_db = await _folders_repository.get_project_to_folder(
                app,
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
                app,
                user_id=user_id,
                new_project=new_project,
                predefined_project=predefined_project,
            )

        # 3.1 save new project in DB
        new_project = await _projects_repository_legacy.insert_project(
            project=jsonable_encoder(new_project),
            user_id=user_id,
            product_name=product_name,
            force_as_template=as_template,
            hidden=copy_data,
            project_nodes=project_nodes,
        )
        # add parent linking if needed
        await set_project_ancestors(
            app,
            user_id=user_id,
            project_uuid=new_project["uuid"],
            parent_project_uuid=parent_project_uuid,
            parent_node_id=parent_node_id,
        )
        await progress.update()

        # 3.2 move project to proper folder
        if folder_id:
            await _folders_repository.insert_project_to_folder(
                app,
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
            await _projects_repository.patch_project(
                app,
                project_uuid=new_project["uuid"],
                new_partial_project_data={"hidden": False},
            )

        # update the network information in director-v2
        await dynamic_scheduler_service.update_projects_networks(
            app, project_id=ProjectID(new_project["uuid"])
        )
        await progress.update()

        # This is a new project and every new graph needs to be reflected in the pipeline tables
        await director_v2_service.create_or_update_pipeline(
            app,
            user_id,
            new_project["uuid"],
            product_name,
            product_api_base_url,
        )
        # get the latest state of the project (lastChangeDate for instance)
        new_project, _ = await _projects_repository_legacy.get_project_dict_and_type(
            project_uuid=new_project["uuid"]
        )
        # Appends state
        new_project = await _projects_service.add_project_states_for_user(
            user_id=user_id,
            project=new_project,
            is_template=as_template,
            app=app,
        )
        await progress.update()

        # Adds permalink
        await update_or_pop_permalink_in_project(app, url, headers, new_project)

        # Adds folderId
        user_specific_project_data_db = (
            await _projects_repository_legacy.get_user_specific_project_data_db(
                project_uuid=new_project["uuid"],
                private_workspace_user_id_or_none=(
                    user_id if workspace_id is None else None
                ),
            )
        )
        new_project["folderId"] = user_specific_project_data_db.folder_id

        # Overwrite project access rights
        if workspace_id:
            workspace: UserWorkspaceWithAccessRights = await get_user_workspace(
                app,
                user_id=user_id,
                workspace_id=workspace_id,
                product_name=product_name,
                permission=None,
            )
            new_project["accessRights"] = {
                f"{gid}": access.model_dump()
                for gid, access in workspace.access_rights.items()
            }

        _project_product_name = await _projects_repository_legacy.get_project_product(
            project_uuid=new_project["uuid"]
        )
        assert (
            _project_product_name == product_name  # nosec
        ), "Project product name mismatch"
        if _project_product_name != product_name:
            raise web.HTTPBadRequest(
                text=f"Project product name mismatch {product_name=} {_project_product_name=}"
            )

        data = ProjectGet.from_domain_model(new_project).model_dump(
            **RESPONSE_MODEL_POLICY
        )

        return web.HTTPCreated(
            text=json_dumps({"data": data}),
            content_type=MIMETYPE_APPLICATION_JSON,
        )

    except JsonSchemaValidationError as exc:
        raise web.HTTPBadRequest(text="Invalid project data") from exc

    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound(text=f"Project {exc.project_uuid} not found") from exc

    except (ProjectInvalidRightsError, WorkspaceAccessForbiddenError) as exc:
        raise web.HTTPForbidden from exc

    except (ParentProjectNotFoundError, ParentNodeNotFoundError) as exc:
        if project_uuid := new_project.get("uuid"):
            await _projects_service.submit_delete_project_task(
                app=app,
                project_uuid=project_uuid,
                user_id=user_id,
                simcore_user_agent=simcore_user_agent,
            )
        raise web.HTTPNotFound(text=f"{exc}") from exc

    except asyncio.CancelledError:
        _logger.warning(
            "cancelled create_project for '%s'. Cleaning up",
            f"{user_id=}",
        )
        if project_uuid := new_project.get("uuid"):
            await _projects_service.submit_delete_project_task(
                app=app,
                project_uuid=project_uuid,
                user_id=user_id,
                simcore_user_agent=simcore_user_agent,
            )
        raise


def register_create_project_task(app: web.Application) -> None:
    TaskRegistry.register_partial(create_project, app=app)
    _logger.debug(
        "I've manged to register the create_project task %s",
        TaskRegistry.REGISTERED_TASKS,
    )
