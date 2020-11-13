# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
from simcore_service_webserver.projects.projects_db import ProjectDBAPI
from simcore_service_webserver.utils import now_str
from simcore_service_webserver import db_models
from simcore_service_webserver.constants import APP_JSONSCHEMA_SPECS_KEY
from simcore_service_webserver.projects import projects_api

# from simcore_service_webserver.viewers_distpacher import *

from models_library.projects import Project, Node, PortLink, AccessRights, StudyUI
import pytest
import json
from pathlib import Path
from typing import Dict


@pytest.fixture
def project_jsonschema(project_schema_file: Path) -> Dict:
    return json.loads(project_schema_file.read_text())


def test_create_project_with_viewer(project_jsonschema):
    # create project with file-picker (download_link) and viewer
    owner_email = "foo@bar.com"
    owner_gid = 3
    owner_uid = 1

    file_picker_id = "4c69c0ce-00e4-4bd5-9cf0-59b67b3a9343"
    file_picker_output_id = "outFile"
    file_picker = Node(
        key="simcore/services/frontend/file-picker",
        version="1.0.0",
        label="File Picker",
        inputs={},
        inputNodes=[],
        outputs={
            # FIXME: ????? No schema??
            file_picker_output_id: {
                "downloadLink": "http://httpbin.org/image/jpeg",
                "label": None,
            }
        },
        progress=100,
    )

    viewer_id = "fc718e5a-bf07-4abe-b526-d9cafd34830c"
    viewer_service = Node(
        key="simcore/services/dynamic/sim4life",
        version="1.0.16",
        label="sim4life",
        inputs={
            "input_1": PortLink(nodeUuid=file_picker_id, output=file_picker_output_id)
        },
        inputNodes=[
            file_picker_id,
        ],
    )

    project = Project(
        uuid="e3ee7dfc-25c3-11eb-9fae-02420a01b846",
        name="Draft Viewer",
        description="Temporary study to visualize downloaded file",
        thumbnail="https://placeimg.com/171/96/tech/grayscale/?0.jpg",
        prjOwner=owner_email,
        accessRights={owner_gid: AccessRights(read=True, write=False, delete=False)},
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

    # can convert to db?
    projects_api.validate_project(
        app={APP_JSONSCHEMA_SPECS_KEY: {"projects": project_jsonschema}},
        project=project.json(),
    )


def test_map_file_types_to_viewers():
    pass


def test_create_guset_use():
    pass


def test_portal_workflow():
    pass
