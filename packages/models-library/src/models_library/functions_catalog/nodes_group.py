from ..services import LATEST_INTEGRATION_VERSION, ServiceDockerData, ServiceType
from ._utils import OM, register
from .constants import FUNCTION_SERVICE_KEY_PREFIX

#
# NOTE: DO not mistake with simcore/services/frontend/nodes-group/macros/
#  which needs to be redefined.
#
META = ServiceDockerData.parse_obj(
    {
        "integration-version": LATEST_INTEGRATION_VERSION,
        "key": f"{FUNCTION_SERVICE_KEY_PREFIX}/nodes-group",
        "version": "1.0.0",
        "type": ServiceType.FRONTEND,
        "name": "Group",
        "description": "Group of nodes",
        "authors": [
            OM,
        ],
        "contact": OM.email,
        "inputs": {},
        "outputs": {
            "outFile": {
                "displayOrder": 0,
                "label": "File",
                "description": "Chosen File",
                "type": "data:*/*",
            }
        },
    }
)


assert META.outputs is not None  # nosec
assert list(META.outputs.keys()) == ["outFile"], "name used in front-end"  # nosec

REGISTRY = register(META)
