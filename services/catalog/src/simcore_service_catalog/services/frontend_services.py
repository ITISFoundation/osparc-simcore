from typing import Any, Dict, Iterator, List

from fastapi import status
from fastapi.exceptions import HTTPException
from models_library.services import ServiceDockerData, ServiceType

FRONTEND_SERVICE_KEY_PREFIX = "simcore/services/frontend"


def create_file_picker_service() -> ServiceDockerData:
    return ServiceDockerData(
        key=f"{FRONTEND_SERVICE_KEY_PREFIX}/file-picker",
        version="1.0.0",
        type=ServiceType.FRONTEND,
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


def create_node_group_service() -> ServiceDockerData:
    return ServiceDockerData(
        key=f"{FRONTEND_SERVICE_KEY_PREFIX}/nodes-group",
        version="1.0.0",
        type=ServiceType.FRONTEND,
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


def create_data_iterator_integer_service() -> ServiceDockerData:
    return ServiceDockerData(
        key=f"{FRONTEND_SERVICE_KEY_PREFIX}/data-iterator/integer",
        version="1.0.0",
        type=ServiceType.FRONTEND,
        name="Data Iterator - Integer",
        description="Data Iterator - Integer",
        authors=[{"name": "Odei Maiz", "email": "maiz@itis.swiss"}],
        contact="maiz@itis.swiss",
        inputs={
            "iteration_type": {
                "displayOrder": 0,
                "label": "Iteration type",
                "description": "Iteration type",
                "defaultValue": "custom",
                "type": "string",
                "widget": {
                    "type": "SelectBox",
                    "structure": [{
                        "key": "custom",
                        "label": "Custom"
                    }, {
                        "key": "linspace",
                        "label": "Linear Space"
                    }, {
                        "key": "random",
                        "label": "Random"
                    }]
                }
            }
        },
        outputs={
            "out_1": {
                "label": "An Integer",
                "description": "An Integer",
                "type": "integer",
            }
        },
    )


def is_frontend_service(service_key) -> bool:
    return service_key.startswith(FRONTEND_SERVICE_KEY_PREFIX + "/")


def iter_service_docker_data() -> Iterator[ServiceDockerData]:
    for factory in [create_file_picker_service, create_node_group_service, create_data_iterator_integer_service]:
        model_instance = factory()
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
