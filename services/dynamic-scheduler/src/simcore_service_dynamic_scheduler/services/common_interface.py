from datetime import timedelta
from typing import Final

from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services import (
    DynamicServiceGet,
    GetProjectInactivityResponse,
    RetrieveDataOutEnveloped,
)
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStart,
    DynamicServiceStop,
)
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services_types import ServicePortKey
from models_library.users import UserID
from pydantic import NonNegativeInt

from ..core.settings import ApplicationSettings
from .catalog._public_client import CatalogPublicClient
from .director_v2 import DirectorV2Client
from .service_tracker import (
    get_tracked_service,
    set_request_as_running,
    set_request_as_stopped,
)

_NEW_STYLE_SERVICES_STOP_TIMEOUT: Final[timedelta] = timedelta(minutes=5)


async def list_tracked_dynamic_services(
    app: FastAPI, *, user_id: UserID | None = None, project_id: ProjectID | None = None
) -> list[DynamicServiceGet]:
    settings: ApplicationSettings = app.state.settings
    if settings.DYNAMIC_SCHEDULER_USE_INTERNAL_SCHEDULER:
        raise NotImplementedError

    director_v2_client = DirectorV2Client.get_from_app_state(app)
    return await director_v2_client.list_tracked_dynamic_services(
        user_id=user_id, project_id=project_id
    )


async def get_service_status(
    app: FastAPI, *, node_id: NodeID
) -> NodeGet | DynamicServiceGet | NodeGetIdle:
    settings: ApplicationSettings = app.state.settings
    if settings.DYNAMIC_SCHEDULER_USE_INTERNAL_SCHEDULER:
        raise NotImplementedError

    director_v2_client = DirectorV2Client.get_from_app_state(app)
    response: NodeGet | DynamicServiceGet | NodeGetIdle = (
        await director_v2_client.get_status(node_id)
    )
    return response


async def run_dynamic_service(
    app: FastAPI, *, dynamic_service_start: DynamicServiceStart
) -> NodeGet | DynamicServiceGet:
    await set_request_as_running(app, dynamic_service_start)

    settings: ApplicationSettings = app.state.settings
    if settings.DYNAMIC_SCHEDULER_USE_INTERNAL_SCHEDULER:
        raise NotImplementedError

    director_v2_client = DirectorV2Client.get_from_app_state(app)
    response: NodeGet | DynamicServiceGet = (
        await director_v2_client.run_dynamic_service(dynamic_service_start)
    )

    return response


async def stop_dynamic_service(
    app: FastAPI, *, dynamic_service_stop: DynamicServiceStop
) -> None:
    await set_request_as_stopped(app, dynamic_service_stop)

    settings: ApplicationSettings = app.state.settings
    if settings.DYNAMIC_SCHEDULER_USE_INTERNAL_SCHEDULER:
        raise NotImplementedError

    # by default assume worst case scenarios:
    # - service is legacy (which can take a long time to stop)
    # - did not find tracked service (assume legacy)
    stop_timeout: timedelta = settings.DYNAMIC_SCHEDULER_STOP_SERVICE_TIMEOUT

    tracked_service = await get_tracked_service(app, dynamic_service_stop.node_id)
    if tracked_service and tracked_service.dynamic_service_start:
        service_labels = await CatalogPublicClient.get_from_app_state(
            app
        ).get_service_labels(
            tracked_service.dynamic_service_start.key,
            tracked_service.dynamic_service_start.version,
        )
        if service_labels.needs_dynamic_sidecar:
            stop_timeout = _NEW_STYLE_SERVICES_STOP_TIMEOUT

    director_v2_client = DirectorV2Client.get_from_app_state(app)
    await director_v2_client.stop_dynamic_service(
        node_id=dynamic_service_stop.node_id,
        simcore_user_agent=dynamic_service_stop.simcore_user_agent,
        save_state=dynamic_service_stop.save_state,
        timeout=stop_timeout,
    )


async def get_project_inactivity(
    app: FastAPI, *, project_id: ProjectID, max_inactivity_seconds: NonNegativeInt
) -> GetProjectInactivityResponse:
    settings: ApplicationSettings = app.state.settings
    if settings.DYNAMIC_SCHEDULER_USE_INTERNAL_SCHEDULER:
        raise NotImplementedError

    director_v2_client = DirectorV2Client.get_from_app_state(app)
    response: GetProjectInactivityResponse = (
        await director_v2_client.get_project_inactivity(
            project_id=project_id, max_inactivity_seconds=max_inactivity_seconds
        )
    )
    return response


async def restart_user_services(app: FastAPI, *, node_id: NodeID) -> None:
    settings: ApplicationSettings = app.state.settings
    if settings.DYNAMIC_SCHEDULER_USE_INTERNAL_SCHEDULER:
        raise NotImplementedError

    director_v2_client = DirectorV2Client.get_from_app_state(app)
    await director_v2_client.restart_user_services(node_id=node_id)


async def retrieve_inputs(
    app: FastAPI, *, node_id: NodeID, port_keys: list[ServicePortKey]
) -> RetrieveDataOutEnveloped:
    settings: ApplicationSettings = app.state.settings
    if settings.DYNAMIC_SCHEDULER_USE_INTERNAL_SCHEDULER:
        raise NotImplementedError

    director_v2_client = DirectorV2Client.get_from_app_state(app)
    return await director_v2_client.retrieve_inputs(
        node_id=node_id,
        port_keys=port_keys,
        timeout=settings.DYNAMIC_SCHEDULER_SERVICE_UPLOAD_DOWNLOAD_TIMEOUT,
    )


async def update_projects_networks(app: FastAPI, *, project_id: ProjectID) -> None:
    settings: ApplicationSettings = app.state.settings
    if settings.DYNAMIC_SCHEDULER_USE_INTERNAL_SCHEDULER:
        raise NotImplementedError

    director_v2_client = DirectorV2Client.get_from_app_state(app)
    await director_v2_client.update_projects_networks(project_id=project_id)
