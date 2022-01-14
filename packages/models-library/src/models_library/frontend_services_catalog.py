"""
    Factory to build catalog of i/o metadata for functions implemented in the front-end

    NOTE: These definitions are currently needed in the catalog and director2
    services. Since it is static data, instead of making a call from
    director2->catalog, it was decided to share as a library
"""

import functools
from typing import Iterator, Optional

from .services import Author, ServiceDockerData, ServiceType

FRONTEND_SERVICE_KEY_PREFIX = "simcore/services/frontend"

OM = Author(name="Odei Maiz", email="maiz@itis.swiss", affiliation="IT'IS")


# FACTORY FUNCTIONS ----------------------------------------------------


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


def _create_constant_node_def(
    output_type: str, output_name: Optional[str] = None
) -> ServiceDockerData:
    """
    Represents a parameter (e.g. x=5) in a study

    This is a parametrized node (or param-node in short)
    """
    LABEL = output_name or f"{output_type.capitalize()} Parameter"
    DESCRIPTION = f"Parameter of type {output_type}"
    output_name = output_name or "out_1"

    meta = ServiceDockerData(
        key=f"{FRONTEND_SERVICE_KEY_PREFIX}/parameter/{output_type}",
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
                "label": output_name,
                "description": DESCRIPTION,
                "type": output_type,
            }
        },
    )

    assert meta.outputs is not None  # nosec
    assert list(meta.outputs.keys()) == ["out_1"], "name used in front-end"  # nosec
    return meta


def _create_data_iterator_int_range() -> ServiceDockerData:
    return ServiceDockerData(
        key=f"{FRONTEND_SERVICE_KEY_PREFIX}/data-iterator/int-range",
        version="1.0.0",
        type=ServiceType.FRONTEND,
        name="Integer iterator",
        description="Integer iterator. range()",
        authors=[
            OM,
        ],
        contact=OM.email,
        inputs={
            "linspace_start": {
                "label": "Start",
                "description": "Linear space Start",
                "defaultValue": 0,
                "type": "integer",
            },
            "linspace_stop": {
                "label": "Stop",
                "description": "Linear space Stop",
                "defaultValue": 1,
                "type": "integer",
            },
            "linspace_step": {
                "label": "Step",
                "description": "Linear space Step",
                "defaultValue": 1,
                "type": "integer",
            },
        },
        outputs={
            "out_1": {
                "label": "An integer",
                "description": "One integer per iteration",
                "type": "integer",
            }
        },
    )


def _create_iterator_consumer_probe_int() -> ServiceDockerData:
    return ServiceDockerData(
        key=f"{FRONTEND_SERVICE_KEY_PREFIX}/iterator-consumer/probe/int",
        version="1.0.0",
        type=ServiceType.FRONTEND,
        name="Probe Sensor - Integer",
        description="Integer iterator consumer.",
        authors=[
            OM,
        ],
        contact=OM.email,
        inputs={
            "in_1": {
                "label": "Iterator consumer",
                "description": "Iterator consumer",
                "defaultValue": 0,
                "type": "integer",
            }
        },
        outputs={},
    )


_FACTORY_FUNCTIONS = [
    _create_file_picker_service,
    _create_node_group_service,
    _create_data_iterator_int_range,
    _create_iterator_consumer_probe_int,
] + [
    functools.partial(_create_constant_node_def, output_type=p)
    for p in ["number", "boolean", "integer"]
]


def iter_service_docker_data() -> Iterator[ServiceDockerData]:
    for create in _FACTORY_FUNCTIONS:
        model_instance = create()
        assert is_frontend_service(model_instance.key)  # nosec
        yield model_instance


# HELPER --------------------------------------


def is_frontend_service(service_key: str) -> bool:
    return service_key.startswith(f"{FRONTEND_SERVICE_KEY_PREFIX}/")


def is_parameter_service(service_key: str) -> bool:
    return service_key.startswith(f"{FRONTEND_SERVICE_KEY_PREFIX}/parameter/")


def is_iterator_service(service_key: str) -> bool:
    return service_key.startswith(f"{FRONTEND_SERVICE_KEY_PREFIX}/data-iterator/")


def is_iterator_consumer_service(service_key: str) -> bool:
    return service_key.startswith(f"{FRONTEND_SERVICE_KEY_PREFIX}/iterator-consumer/")
