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


def create_parametrization_const_number() -> ServiceDockerData:
    return ServiceDockerData(
        key=f"{FRONTEND_SERVICE_KEY_PREFIX}/parameter/number",
        version="1.0.0",
        type=ServiceType.FRONTEND,
        name="Number Parameter",
        description="",
        authors=[{"name": "Odei Maiz", "email": "maiz@itis.swiss"}],
        contact="maiz@itis.swiss",
        inputs={},
        outputs={
            "out_1": {
                "displayOrder": 0,
                "label": "Number Parameter",
                "description": "",
                "type": "number",
            }
        },
    )


def create_parametrization_const_integer() -> ServiceDockerData:
    return ServiceDockerData(
        key=f"{FRONTEND_SERVICE_KEY_PREFIX}/parameter/integer",
        version="1.0.0",
        type=ServiceType.FRONTEND,
        name="Integer Parameter",
        description="",
        authors=[{"name": "Odei Maiz", "email": "maiz@itis.swiss"}],
        contact="maiz@itis.swiss",
        inputs={},
        outputs={
            "out_1": {
                "displayOrder": 0,
                "label": "Integer Parameter",
                "description": "",
                "type": "integer",
            }
        },
    )


def create_parametrization_const_boolean() -> ServiceDockerData:
    return ServiceDockerData(
        key=f"{FRONTEND_SERVICE_KEY_PREFIX}/parameter/boolean",
        version="1.0.0",
        type=ServiceType.FRONTEND,
        name="Boolean Parameter",
        description="",
        authors=[{"name": "Odei Maiz", "email": "maiz@itis.swiss"}],
        contact="maiz@itis.swiss",
        inputs={},
        outputs={
            "out_1": {
                "displayOrder": 0,
                "label": "Boolean Parameter",
                "description": "",
                "type": "boolean",
            }
        },
    )


def create_data_iterator_integer_service() -> ServiceDockerData:
    return ServiceDockerData(
        key=f"{FRONTEND_SERVICE_KEY_PREFIX}/data-iterator/number",
        version="1.0.0",
        type=ServiceType.FRONTEND,
        name="Number Iterator",
        description="Data Iterator - Number",
        authors=[{
            "name": "Odei Maiz",
            "email": "maiz@itis.swiss"
        }],
        contact="maiz@itis.swiss",
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


def is_frontend_service(service_key) -> bool:
    return service_key.startswith(FRONTEND_SERVICE_KEY_PREFIX + "/")


def iter_service_docker_data() -> Iterator[ServiceDockerData]:
    for factory in [
        create_file_picker_service,
        create_parametrization_const_number,
        create_parametrization_const_integer,
        create_parametrization_const_boolean,
        create_data_iterator_integer_service,
        create_node_group_service
    ]:
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
