""" Projects management

 Keeps functionality that couples with the following app modules
    - projects


"""
from models_library.projects import AccessRights, Node, PortLink, Project, StudyUI

from ..utils import now_str
from ._core import ViewerInfo
from ._users import UserInfo


async def has_user_access(user: UserInfo, project_id: str) -> bool:
    pass


async def save_project(project: Project, user_id):

    pass


async def create_viewer_project_model(
    project_id: str,
    owner: UserInfo,
    download_link: str,
    viewer_info: ViewerInfo,
) -> Project:
    # TODO: generate ids

    file_picker_id = "4c69c0ce-00e4-4bd5-9cf0-59b67b3a9343"
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

    viewer_id = "fc718e5a-bf07-4abe-b526-d9cafd34830c"
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
        # TODO: check implications with SAN
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
