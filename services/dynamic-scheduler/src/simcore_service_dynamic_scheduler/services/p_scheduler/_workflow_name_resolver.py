from enum import auto

from fastapi import FastAPI
from models_library.api_schemas_dynamic_scheduler.dynamic_services import DynamicServiceStart, DynamicServiceStop
from models_library.utils.enums import StrAutoEnum

from ..catalog import CatalogPublicClient
from ..director_v0 import DirectorV0PublicClient
from ._models import WorkflowName


class _WorkflowType(StrAutoEnum):
    START = auto()
    STOP = auto()


class _DynamicServiceTypes(StrAutoEnum):
    LEGACY = auto()
    NEW_STYLE = auto()


async def get_service_start_workflow_name(app: FastAPI, *, service_start: DynamicServiceStart) -> WorkflowName:
    catalog_client = CatalogPublicClient.get_from_app_state(app)
    service_labels = await catalog_client.get_docker_image_labels(
        service_key=service_start.key, service_version=service_start.version
    )

    service_type = (
        _DynamicServiceTypes.NEW_STYLE if service_labels.needs_dynamic_sidecar else _DynamicServiceTypes.LEGACY
    )

    return f"{_WorkflowType.START}_{service_type}"


async def get_service_stop_workflow_name(app: FastAPI, *, service_stop: DynamicServiceStop) -> WorkflowName:
    client = DirectorV0PublicClient.get_from_app_state(app)
    node_details = client.get_running_service_details(service_stop.node_id)

    # NOTE: we assume that if the service is not present as LEGACY, it's going to be NEW_STYLE
    workflow_type = _DynamicServiceTypes.LEGACY if node_details is not None else _DynamicServiceTypes.NEW_STYLE
    return f"{_WorkflowType.STOP}_{workflow_type}"
