"""
    Catalog of i/o metadata for functions implemented in the front-end
"""


import functools
from typing import Any, Dict, Iterator, List

from fastapi import status
from fastapi.exceptions import HTTPException
from models_library.services import ServiceDockerData, ServiceType

FRONTEND_SERVICE_KEY_PREFIX = "simcore/services/frontend"
OM = {"name": "Odei Maiz", "email": "maiz@itis.swiss"}


def create_file_picker_service() -> ServiceDockerData:
    return ServiceDockerData(
        key=f"{FRONTEND_SERVICE_KEY_PREFIX}/file-picker",
        version="1.0.0",
        type=ServiceType.FRONTEND,
        name="File Picker",
        description="File Picker",
        authors=[
            OM,
        ],
        contact=OM["email"],
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


def create_node_group_service() -> ServiceDockerData:
    return ServiceDockerData(
        key=f"{FRONTEND_SERVICE_KEY_PREFIX}/nodes-group",
        version="1.0.0",
        type=ServiceType.FRONTEND,
        name="Group",
        description="Group of nodes",
        authors=[
            OM,
        ],
        contact=OM["email"],
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


def create_parameter(param_type: str) -> ServiceDockerData:
    """
    Represents a parameter (e.g. x=5) in a study

    This is a parametrized node (or param-node in short)
    """
    assert param_type in ["number", "boolean", "integer"]  # nosec

    LABEL = f"{param_type.capitalize()} Parameter"
    DESCRIPTION = (f"Parameter of type {param_type}",)

    meta = ServiceDockerData(
        key=f"{FRONTEND_SERVICE_KEY_PREFIX}/parameter/{param_type}",
        version="1.0.0",
        type=ServiceType.FRONTEND,
        name=LABEL,
        description=DESCRIPTION,
        authors=[
            OM,
        ],
        contact=OM["email"],
        inputs={},
        outputs={
            "out_1": {
                "label": LABEL,
                "description": DESCRIPTION,
                "type": param_type,
            }
        },
    )

    assert meta.outputs  # nosec
    assert list(meta.outputs.keys()) == ["out_1"], "name used in front-end"  # nosec
    return meta


def is_frontend_service(service_key: str) -> bool:
    return service_key.startswith(FRONTEND_SERVICE_KEY_PREFIX + "/")


_factory_functions = [create_file_picker_service, create_node_group_service,] + [
    functools.partial(create_parameter, param_type=p)
    for p in ["number", "boolean", "integer"]
]


def iter_service_docker_data() -> Iterator[ServiceDockerData]:
    for create in _factory_functions:
        model_instance = create()
        yield model_instance


def as_dict(model_instance: ServiceDockerData) -> Dict[str, Any]:
    # FIXME: In order to convert to ServiceOut, now we have to convert back to front-end service because of alias
    # FIXME: set the same policy for f/e and director datasets!
    return model_instance.dict(by_alias=True, exclude_unset=True)


def list_frontend_services() -> List[Dict[str, Any]]:
    return [as_dict(s) for s in iter_service_docker_data()]


def get_frontend_service(key, version) -> Dict[str, Any]:
    try:
        found = next(
            s
            for s in iter_service_docker_data()
            if s.key == key and s.version == version
        )
        return as_dict(found)
    except StopIteration as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Frontend service '{key}:{version}' not found",
        ) from err
