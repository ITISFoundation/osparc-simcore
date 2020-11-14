""" Projects management

 Keeps functionality that couples with the following app modules
    - projects


"""
from models_library.projects import AccessRights, Node, PortLink, Project, StudyUI

from ..utils import now_str


async def create_viewer_project_model(
    owner_email, owner_groupid, download_link, viewer_key, viewer_version, viewer_label,
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
        key=viewer_key,
        version=viewer_version,
        label=viewer_label,
        inputs={
            "input_1": PortLink(nodeUuid=file_picker_id, output=file_picker_output_id)
        },
        inputNodes=[
            file_picker_id,
        ],
    )

    project_id = "e3ee7dfc-25c3-11eb-9fae-02420a01b846"
    project = Project(
        uuid= project_id,
        name="Draft Viewer",
        description="Temporary study to visualize downloaded file",
        thumbnail="https://placeimg.com/171/96/tech/grayscale/?0.jpg",
        prjOwner=owner_email,
        accessRights={
            owner_groupid: AccessRights(read=True, write=False, delete=False)
        },
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
