from ..services import Author, ServiceDockerData, ServiceType
from ._constants import FRONTEND_SERVICE_KEY_PREFIX

OM = Author(name="Odei Maiz", email="maiz@itis.swiss", affiliation="IT'IS")


def create_metadata() -> ServiceDockerData:
    return ServiceDockerData(
        key=f"{FRONTEND_SERVICE_KEY_PREFIX}/file-picker",
        version="1.0.0",
        type=ServiceType.FRONTEND,
        name="File Picker",
        description="File Picker",
        authors=[
            OM,
        ],
        contact=OM.email,
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
