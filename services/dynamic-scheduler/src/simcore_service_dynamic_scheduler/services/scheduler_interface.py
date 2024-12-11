from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStart,
    DynamicServiceStop,
)
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID

from ..core.settings import ApplicationSettings
from .director_v2 import DirectorV2Client
from .service_tracker import set_request_as_running, set_request_as_stopped


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
    settings: ApplicationSettings = app.state.settings
    if settings.DYNAMIC_SCHEDULER_USE_INTERNAL_SCHEDULER:
        raise NotImplementedError

    director_v2_client = DirectorV2Client.get_from_app_state(app)
    response: NodeGet | DynamicServiceGet = (
        await director_v2_client.run_dynamic_service(dynamic_service_start)
    )

    await set_request_as_running(app, dynamic_service_start)
    return response


async def stop_dynamic_service(
    app: FastAPI, *, dynamic_service_stop: DynamicServiceStop
) -> None:
    settings: ApplicationSettings = app.state.settings
    if settings.DYNAMIC_SCHEDULER_USE_INTERNAL_SCHEDULER:
        raise NotImplementedError

    director_v2_client = DirectorV2Client.get_from_app_state(app)
    await director_v2_client.stop_dynamic_service(
        node_id=dynamic_service_stop.node_id,
        simcore_user_agent=dynamic_service_stop.simcore_user_agent,
        save_state=dynamic_service_stop.save_state,
        timeout=settings.DYNAMIC_SCHEDULER_STOP_SERVICE_TIMEOUT,
    )

    await set_request_as_stopped(app, dynamic_service_stop)
