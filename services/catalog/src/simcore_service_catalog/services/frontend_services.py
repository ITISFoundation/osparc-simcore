from typing import List

from models_library.services import ServiceDockerData


def _file_picker_service() -> ServiceDockerData:
    # TODO: create once and just create copies here
    return ServiceDockerData(
        key="simcore/services/frontend/file-picker",
        version="1.0.0",
        type="dynamic",
        name="File Picker",
        description="File Picker",
        authors=[{"name": "Odei Maiz", "email": "maiz@itis.swiss"}],
        contact="maiz@itis.swiss",
        inputs={},
        outputs={
            "outFile": {
                "displayOrder": 0,
                "label": "File",
                "description": "Chosen File",
                "type": "data:*/*",
            }
        },
    )


def _node_group_service() -> ServiceDockerData:
    return ServiceDockerData(
        key="simcore/services/frontend/nodes-group",
        version="1.0.0",
        type="frontend",
        name="Group",
        description="Group of nodes",
        authors=[{"name": "Odei Maiz", "email": "maiz@itis.swiss"}],
        contact="maiz@itis.swiss",
        inputs={},
        outputs={
            "outFile": {
                "displayOrder": 0,
                "label": "File",
                "description": "Chosen File",
                "type": "data:*/*",
            }
        },
    )


def get_services() -> List[ServiceDockerData]:
    return [_file_picker_service(), _node_group_service()]
