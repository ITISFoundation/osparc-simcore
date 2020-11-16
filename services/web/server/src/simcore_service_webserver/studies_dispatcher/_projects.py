""" Projects management

 Keeps functionality that couples with the following app modules
    - projects
    - TMP: add_new_project includes to projects and computations app modules!

"""
import json
import logging
from typing import Dict, Tuple

from aiohttp import web
from pydantic import HttpUrl

from models_library.projects import AccessRights, Node, PortLink, Project, StudyUI

from ..projects_api import get_project_for_user
from ..projects_exceptions import ProjectInvalidRightsError, ProjectNotFoundError
from ..utils import now_str
from ._core import ViewerInfo, compose_uuid_from
from ._users import UserInfo

log = logging.getLogger(__name__)


async def acquire_project_with_viewer(
    app: web.Application, user: UserInfo, viewer: ViewerInfo, download_link: HttpUrl
) -> Tuple[str, str]:
    #
    # Generate one project per user + download_link + viewer
    #   - if user requests several times, the same project is reused
    #   - if user is not a guest, the project will be saved in it's account (desired?)
    #
    project_id = compose_uuid_from(user.id, viewer.footprint, download_link)

    # Ids are linked to produce a footprint (see viewer_project_exists)
    file_picker_id, viewer_id = generate_nodeids(project_id)

    try:
        project_db: Dict = await get_project_for_user(
            app, project_id, user.id, include_templates=False, include_state=False
        )

        # check if viewer already created by this app module
        valid_viewer = {file_picker_id, viewer_id} == set(
            project_db.get("workbench", {}).keys()
        )
        if valid_viewer:
            viewer_exists = True
        else:
            log.error(
                "Project %s exists but does not seem to be a viewer generated by this module."
                " user: %s, viwere:%s, download_link:%s",
                project_id,
                user,
                viewer,
                download_link,
            )
            # FIXME: CANNOT GUARANTEE!!, DELETE?? ERROR?? and cannot be viewed until verified?
            raise web.HTTPInternalServerError()

    except (ProjectNotFoundError, ProjectInvalidRightsError):
        viewer_exists = False

    if not viewer_exists:
        project = await create_viewer_project_model(
            project_id, file_picker_id, viewer_id, user, download_link, viewer
        )
        await add_new_project(app, project, user)

    return project_id, viewer_id


# UTILITIES -------------------------------------------------


def generate_nodeids(project_id: str) -> Tuple[str, str]:
    file_picker_id = compose_uuid_from(
        project_id, "4c69c0ce-00e4-4bd5-9cf0-59b67b3a9343"
    )
    viewer_id = compose_uuid_from(project_id, "fc718e5a-bf07-4abe-b526-d9cafd34830c")
    return file_picker_id, viewer_id


async def create_viewer_project_model(
    project_id: str,
    file_picker_id: str,
    viewer_id: str,
    owner: UserInfo,
    download_link: str,
    viewer_info: ViewerInfo,
) -> Project:

    file_picker_output_id = "outFile"
    file_picker = Node(
        key="simcore/services/frontend/file-picker",
        version="1.0.0",
        label="File Picker",
        inputs={},
        inputNodes=[],
        outputs={
            file_picker_output_id: {
                "downloadLink": download_link,
                "label": None,
            }
        },
        progress=100,
    )

    viewer_service = Node(
        key=viewer_info.key,
        version=viewer_info.version,
        label=viewer_info.label,
        inputs={
            "input_1": PortLink(nodeUuid=file_picker_id, output=file_picker_output_id)
        },
        inputNodes=[
            file_picker_id,
        ],
    )

    # Access rights policy
    access_rights = AccessRights(read=True, write=True, delete=True)  # will keep a copy
    if owner.is_guest:
        # TODO: check implications with SAN??
        access_rights.write = access_rights.delete = False

    project = Project(
        uuid=project_id,
        name="Draft Viewer",
        description="Temporary study to visualize downloaded file",
        thumbnail="https://placeimg.com/171/96/tech/grayscale/?0.jpg",
        prjOwner=owner.email,
        accessRights={owner.primary_gid: access_rights},
        creationDate=now_str(),
        lastChangeDate=now_str(),
        workbench={file_picker_id: file_picker, viewer_id: viewer_service},
        ui=StudyUI(
            workbench={
                file_picker_id: {"position": {"x": 305, "y": 229}},
                viewer_id: {"position": {"x": 633, "y": 318}},
            }
        ),
    )

    return project


async def add_new_project(app: web.Application, project: Project, user: UserInfo):
    # TODO: move this to projects_api
    # TODO: this piece was taking fromt the end of projects.projects_handlers.create_projects

    from ..projects_db import APP_PROJECT_DBAPI
    from ..computation_api import update_pipeline_db

    db = app[APP_PROJECT_DBAPI]

    # validated project is transform in dict via json to use only primitive types
    project_in: Dict = json.loads(project.json())

    # update metadata (uuid, timestamps, ownership) and save
    project_db: Dict = await db.add_project(
        project_in, user.id, force_as_template=False
    )

    # This is a new project and every new graph needs to be reflected in the pipeline db
    await update_pipeline_db(app, project_db["uuid"], project_db["workbench"])
