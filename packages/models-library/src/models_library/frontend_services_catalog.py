"""
    Factory to build catalog of i/o metadata for functions implemented in the front-end

    NOTE: These definitions are currently needed in the catalog and director2
    services. Since it is static data, instead of making a call from
    director2->catalog, it was decided to share as a library
"""

import functools
from typing import Iterator

from .services import Author, ServiceDockerData, ServiceType

FRONTEND_SERVICE_KEY_PREFIX = "simcore/services/frontend"

OM = Author(name="Odei Maiz", email="maiz@itis.swiss", affiliation="IT'IS")


def _create_file_picker_service() -> ServiceDockerData:
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


def _create_node_group_service() -> ServiceDockerData:
    #
    # NOTE: DO not mistake with simcore/services/frontend/nodes-group/macros/
    #  which needs to be redefined.
    #
    meta = ServiceDockerData(
        key=f"{FRONTEND_SERVICE_KEY_PREFIX}/nodes-group",
        version="1.0.0",
        type=ServiceType.FRONTEND,
        name="Group",
        description="Group of nodes",
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

    assert meta.outputs is not None  # nosec
    assert list(meta.outputs.keys()) == ["outFile"], "name used in front-end"  # nosec
    return meta


def _create_parameter(param_type: str) -> ServiceDockerData:
    """
    Represents a parameter (e.g. x=5) in a study

    This is a parametrized node (or param-node in short)
    """
    assert param_type in ["number", "boolean", "integer"]  # nosec

    LABEL = f"{param_type.capitalize()} Parameter"
    DESCRIPTION = f"Parameter of type {param_type}"

    meta = ServiceDockerData(
        key=f"{FRONTEND_SERVICE_KEY_PREFIX}/parameter/{param_type}",
        version="1.0.0",
        type=ServiceType.FRONTEND,
        name=LABEL,
        description=DESCRIPTION,
        authors=[
            OM,
        ],
        contact=OM.email,
        inputs={},
        outputs={
            "out_1": {
                "label": LABEL,
                "description": DESCRIPTION,
                "type": param_type,
            }
        },
    )

    assert meta.outputs is not None  # nosec
    assert list(meta.outputs.keys()) == ["out_1"], "name used in front-end"  # nosec
    return meta


def _create_data_iterator_integer_service() -> ServiceDockerData:
    return ServiceDockerData(
        key=f"{FRONTEND_SERVICE_KEY_PREFIX}/data-iterator/number",
        version="1.0.0",
        type=ServiceType.FRONTEND,
        name="Number Iterator",
        description="Data Iterator - Number",
        authors=[
            OM,
        ],
        contact=OM.email,
        inputs={
            "iteration_type": {
                "displayOrder": 0,
                "label": "Iteration method",
                "description": "Iteration method",
                "defaultValue": "custom",
                "type": "string",
                "widget": {
                    "type": "SelectBox",
                    "details": {
                        "structure": [{
                            "key": "custom",
                            "label": "Custom",
                        }, {
                            "key": "linspace",
                            "label": "Linear Space",
                        }, {
                            "key": "random",
                            "label": "Random",
                        }]
                    }
                }
            },
            "custom_list": {
                "displayOrder": 1,
                "label": "Custom List",
                "description": "Type your list of numbers (comma separated)",
                "defaultValue": "",
                "type": "string",
            },
            "linspace_start": {
                "displayOrder": 2,
                "label": "Start",
                "description": "Linear space Start",
                "defaultValue": 0,
                "type": "number",
            },
            "linspace_stop": {
                "displayOrder": 3,
                "label": "Stop",
                "description": "Linear space Stop",
                "defaultValue": 1,
                "type": "number",
            },
            "linspace_step": {
                "displayOrder": 4,
                "label": "Step",
                "description": "Linear space Step",
                "defaultValue": 1,
                "type": "number",
            },
            "random_start": {
                "displayOrder": 5,
                "label": "Start",
                "description": "Random Start",
                "defaultValue": 0,
                "type": "number",
            },
            "random_stop": {
                "displayOrder": 6,
                "label": "Stop",
                "description": "Random Stop",
                "defaultValue": 10,
                "type": "number",
            },
            "random_vals": {
                "displayOrder": 7,
                "label": "N values",
                "description": "N Random values",
                "defaultValue": 5,
                "type": "number",
            },
        },
        outputs={
            "out_1": {
                "displayOrder": 0,
                "label": "A Number",
                "description": "A Number",
                "type": "number",
            }
        },
    )


def is_frontend_service(service_key: str) -> bool:
    return service_key.startswith(f"{FRONTEND_SERVICE_KEY_PREFIX}/")


def is_parameter_service(service_key: str) -> bool:
    return service_key.startswith(f"{FRONTEND_SERVICE_KEY_PREFIX}/parameter/")


_FACTORY_FUNCTIONS = [
    _create_file_picker_service,
    _create_node_group_service,
    _create_data_iterator_integer_service,] + [
    functools.partial(_create_parameter, param_type=p)
    for p in ["number", "boolean", "integer"]
]


def iter_service_docker_data() -> Iterator[ServiceDockerData]:
    for create in _FACTORY_FUNCTIONS:
        model_instance = create()
        yield model_instance
