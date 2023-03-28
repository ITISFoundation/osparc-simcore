""" Projects management

 Keeps functionality that couples with the following app modules
    - projects
    - TMP: add_new_project includes to projects and director_v2 app modules!

"""
import json
import logging
from typing import cast

from aiohttp import web
from models_library.projects import AccessRights, Project, ProjectID
from models_library.projects_nodes import Node, NodeID
from models_library.projects_nodes_io import DownloadLink, PortLink
from models_library.projects_ui import StudyUI
from models_library.services import ServiceKey, ServiceVersion
from pydantic import AnyUrl, HttpUrl, parse_obj_as

from ..projects.projects_api import get_project_for_user
from ..projects.projects_db import ProjectDBAPI
from ..projects.projects_exceptions import (
    ProjectInvalidRightsError,
    ProjectNotFoundError,
)
from ..utils import now_str
from ._core import ViewerInfo, compose_uuid_from
from ._users import UserInfo

logger = logging.getLogger(__name__)


_FILE_PICKER_KEY = parse_obj_as(ServiceKey, "simcore/services/frontend/file-picker")
_FILE_PICKER_VERSION = parse_obj_as(ServiceVersion, "1.0.0")


def _generate_nodeids(project_id: ProjectID) -> tuple[NodeID, NodeID]:
    file_picker_id = compose_uuid_from(
        project_id,
        "4c69c0ce-00e4-4bd5-9cf0-59b67b3a9343",
    )
    viewer_id = compose_uuid_from(
        project_id,
        "fc718e5a-bf07-4abe-b526-d9cafd34830c",
    )
    return file_picker_id, viewer_id


def _create_file_picker(download_link: str):
    output_id = "outFile"
    node = Node(
        key=_FILE_PICKER_KEY,
        version=_FILE_PICKER_VERSION,
        label="File Picker",
        inputs={},
        inputNodes=[],
        outputs={
            # NOTE: Empty label checked with @odeimaiz
            output_id: DownloadLink(
                downloadLink=parse_obj_as(AnyUrl, download_link),
                label="",
            )
        },
        progress=0,
    )
    return node, output_id


def _create_project_with_service(
    project_id: ProjectID,
    viewer_id: NodeID,
    owner: UserInfo,
    viewer_info: ViewerInfo,
    *,
    project_thumbnail: HttpUrl = cast(
        HttpUrl, "https://via.placeholder.com/170x120.png"
    ),
) -> Project:

    viewer_service = Node(
        key=viewer_info.key,
        version=viewer_info.version,
        label=viewer_info.label,
        inputs=None,
    )

    # TODO: common!

    # Access rights policy
    access_rights = AccessRights(read=True, write=True, delete=True)  # will keep a copy
    if owner.is_guest:
        access_rights.write = access_rights.delete = False

    # Assambles project instance
    project = Project(
        uuid=project_id,
        name=f"Viewer {viewer_info.title}",
        description="Temporary study to visualize downloaded file",
        thumbnail=project_thumbnail,
        prjOwner=owner.email,  # type: ignore
        accessRights={owner.primary_gid: access_rights},
        creationDate=now_str(),
        lastChangeDate=now_str(),
        workbench={  # type: ignore
            f"{viewer_id}": viewer_service,
        },
        ui=StudyUI(
            workbench={  # type: ignore
                f"{file_picker_id}": {"position": {"x": 305, "y": 229}},
                f"{viewer_id}": {"position": {"x": 633, "y": 229}},
            }
        ),
    )

    return project


def _create_project_with_filepicker_and_service(
    project_id: ProjectID,
    file_picker_id: NodeID,
    viewer_id: NodeID,
    owner: UserInfo,
    download_link: HttpUrl,
    viewer_info: ViewerInfo,
    *,
    project_thumbnail: HttpUrl = cast(
        HttpUrl, "https://via.placeholder.com/170x120.png"
    ),
) -> Project:

    file_picker, file_picker_output_id = _create_file_picker(download_link)

    viewer_service = Node(
        key=viewer_info.key,
        version=viewer_info.version,
        label=viewer_info.label,
        inputs={
            viewer_info.input_port_key: PortLink(
                nodeUuid=file_picker_id,
                output=file_picker_output_id,
            )
        },
        inputNodes=[
            file_picker_id,
        ],
    )

    # Access rights policy
    access_rights = AccessRights(read=True, write=True, delete=True)  # will keep a copy
    if owner.is_guest:
        access_rights.write = access_rights.delete = False

    # Assambles project instance
    project = Project(
        uuid=project_id,
        name=f"Viewer {viewer_info.title}",
        description="Temporary study to visualize downloaded file",
        thumbnail=project_thumbnail,
        prjOwner=owner.email,  # type: ignore
        accessRights={owner.primary_gid: access_rights},
        creationDate=now_str(),
        lastChangeDate=now_str(),
        workbench={  # type: ignore
            f"{file_picker_id}": file_picker,
            f"{viewer_id}": viewer_service,
        },
        ui=StudyUI(
            workbench={  # type: ignore
                f"{file_picker_id}": {"position": {"x": 305, "y": 229}},
                f"{viewer_id}": {"position": {"x": 633, "y": 229}},
            }
        ),
    )

    return project


async def _add_new_project(
    app: web.Application, project: Project, user: UserInfo, *, product_name: str
):
    # TODO: move this to projects_api
    # TODO: this piece was taken from the end of projects.projects_handlers.create_projects

    from ..director_v2_api import create_or_update_pipeline
    from ..projects.projects_db import APP_PROJECT_DBAPI

    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]

    # validated project is transform in dict via json to use only primitive types
    project_in: dict = json.loads(project.json(exclude_none=True, by_alias=True))

    # update metadata (uuid, timestamps, ownership) and save
    _project_db: dict = await db.insert_project(
        project_in, user.id, product_name=product_name, force_as_template=False
    )
    assert _project_db["uuid"] == str(project.uuid)  # nosec

    # This is a new project and every new graph needs to be reflected in the pipeline db
    #
    # TODO: Ensure this user has access to these services!
    #
    await create_or_update_pipeline(app, user.id, project.uuid, product_name)


async def acquire_project_with_viewer(
    app: web.Application,
    user: UserInfo,
    viewer: ViewerInfo,
    download_link: HttpUrl,
    *,
    product_name: str,
) -> tuple[str, str]:
    #
    # Generate one project per user + download_link + viewer
    #   - if user requests several times, the same project is reused
    #   - if user is not a guest, the project will be saved in it's account (desired?)
    #
    project_uid: ProjectID = compose_uuid_from(user.id, viewer.footprint, download_link)

    # Ids are linked to produce a footprint (see viewer_project_exists)
    file_picker_id, viewer_id = _generate_nodeids(project_uid)

    try:
        project_db: dict = await get_project_for_user(
            app, f"{project_uid}", user.id, include_state=False
        )

        # check if viewer already created by this app module
        valid_viewer = {file_picker_id, viewer_id} == set(
            project_db.get("workbench", {}).keys()
        )
        if valid_viewer:
            viewer_exists = True
        else:
            logger.error(
                "Project %s exists but does not seem to be a viewer generated by this module."
                " user: %s, viewer:%s, download_link:%s",
                project_uid,
                user,
                viewer,
                download_link,
            )
            # FIXME: CANNOT GUARANTEE!!, DELETE?? ERROR?? and cannot be viewed until verified?
            raise web.HTTPInternalServerError()

    except (ProjectNotFoundError, ProjectInvalidRightsError):
        viewer_exists = False

    if not viewer_exists:

        project = _create_project_with_filepicker_and_service(
            project_uid,
            file_picker_id,
            viewer_id,
            user,
            download_link,
            viewer,
        )

        await _add_new_project(app, project, user, product_name=product_name)

    return f"{project_uid}", f"{viewer_id}"
