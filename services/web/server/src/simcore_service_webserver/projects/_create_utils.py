import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Any, Coroutine

from aiohttp import web
from jsonschema import ValidationError as JsonSchemaValidationError
from models_library.projects import ProjectID
from models_library.projects_state import ProjectStatus
from models_library.users import UserID
from pydantic import parse_obj_as
from servicelib.aiohttp.long_running_tasks.server import TaskProgress
from servicelib.json_serialization import json_dumps
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from simcore_postgres_database.webserver_models import ProjectType as ProjectTypeDB

from .. import director_v2_api
from ..application_settings import get_settings
from ..storage_api import (
    copy_data_folders_from_project,
    get_project_total_size_simcore_s3,
)
from ..users_api import get_user_name
from . import projects_api
from .project_models import ProjectDict
from .projects_db import APP_PROJECT_DBAPI, ProjectDBAPI
from .projects_exceptions import ProjectInvalidRightsError, ProjectNotFoundError
from .projects_utils import NodesMap, clone_project_document, default_copy_project_name

OVERRIDABLE_DOCUMENT_KEYS = [
    "name",
    "description",
    "thumbnail",
    "prjOwner",
    "accessRights",
]


log = logging.getLogger(__name__)


async def _prepare_project_copy(
    app: web.Application,
    *,
    user_id: UserID,
    src_project_uuid: ProjectID,
    as_template: bool,
    deep_copy: bool,
    task_progress: TaskProgress,
) -> tuple[ProjectDict, Coroutine[Any, Any, None] | None]:
    source_project = await projects_api.get_project_for_user(
        app,
        project_uuid=f"{src_project_uuid}",
        user_id=user_id,
    )
    settings = get_settings(app).WEBSERVER_PROJECTS
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
    return new_project, copy_file_coro


async def _copy_files_from_source_project(
    app: web.Application,
    source_project: ProjectDict,
    new_project: ProjectDict,
    nodes_map: NodesMap,
    user_id: UserID,
    task_progress: TaskProgress,
):
    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]
    needs_lock_source_project: bool = (
        await db.get_project_type(parse_obj_as(ProjectID, source_project["uuid"]))
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
                    await get_user_name(app, user_id),
                )
            )
        starting_value = task_progress.percent
        async for long_running_task in copy_data_folders_from_project(
            app, source_project, new_project, nodes_map, user_id
        ):
            task_progress.update(
                message=long_running_task.progress.message,
                percent=(
                    starting_value
                    + long_running_task.progress.percent * (1.0 - starting_value)
                ),
            )
            if long_running_task.done():
                await long_running_task.result()


async def create_project(
    task_progress: TaskProgress,
    app: web.Application,
    new_project_was_hidden_before_data_was_copied: bool,
    from_study: ProjectID | None,
    as_template: bool,
    copy_data: bool,
    user_id: UserID,
    product_name: str,
    predefined_project: ProjectDict | None,
    simcore_user_agent: str,
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

    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]

    new_project = {}
    copy_file_coro = None
    try:
        task_progress.update(message="creating new study...")
        if from_study:
            # 1. prepare copy
            new_project, copy_file_coro = await _prepare_project_copy(
                app,
                user_id=user_id,
                src_project_uuid=from_study,
                as_template=as_template,
                deep_copy=copy_data,
                task_progress=task_progress,
            )

        if predefined_project:
            # 2. overrides with optional body and re-validate
            if new_project:
                for key in OVERRIDABLE_DOCUMENT_KEYS:
                    if non_null_value := predefined_project.get(key):
                        new_project[key] = non_null_value
            else:
                # TODO: take skeleton and fill instead
                new_project = predefined_project
            await projects_api.validate_project(app, new_project)

        # 3. save new project in DB
        new_project = await db.insert_project(
            new_project,
            user_id,
            product_name=product_name,
            force_as_template=as_template,
            hidden=copy_data,
        )

        # 4. deep copy source project's files
        if copy_file_coro:
            # NOTE: storage needs to have access to the new project prior to copying files
            await copy_file_coro

        # 5. unhide the project if needed since it is now complete
        if not new_project_was_hidden_before_data_was_copied:
            await db.update_project_without_checking_permissions(
                new_project, new_project["uuid"], hidden=False
            )

        # update the network information in director-v2
        await director_v2_api.update_dynamic_service_networks_in_project(
            app, ProjectID(new_project["uuid"])
        )

        # This is a new project and every new graph needs to be reflected in the pipeline tables
        await director_v2_api.create_or_update_pipeline(
            app, user_id, new_project["uuid"], product_name
        )

        # Appends state
        new_project = await projects_api.add_project_states_for_user(
            user_id=user_id,
            project=new_project,
            is_template=as_template,
            app=app,
        )

        raise web.HTTPCreated(
            text=json_dumps({"data": new_project}),
            content_type=MIMETYPE_APPLICATION_JSON,
        )

    except JsonSchemaValidationError as exc:
        raise web.HTTPBadRequest(reason="Invalid project data") from exc
    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"Project {exc.project_uuid} not found") from exc
    except ProjectInvalidRightsError as exc:
        raise web.HTTPUnauthorized from exc
    except asyncio.CancelledError:
        log.warning(
            "cancelled creation of project for '%s', cleaning up",
            f"{user_id=}",
        )
        # FIXME: If cancelled during shutdown, cancellation of all_tasks will produce "new tasks"!
        if prj_uuid := new_project.get("uuid"):
            await projects_api.submit_delete_project_task(
                app, prj_uuid, user_id, simcore_user_agent
            )
        raise
