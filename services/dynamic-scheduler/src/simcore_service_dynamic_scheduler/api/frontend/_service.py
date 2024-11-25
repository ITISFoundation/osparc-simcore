import json

from models_library.projects_nodes_io import NodeID
from nicegui import APIRouter, app, ui
from servicelib.rabbitmq.rpc_interfaces.dynamic_scheduler.services import (
    DynamicServiceStop,
    stop_dynamic_service,
)
from simcore_service_dynamic_scheduler.services.rabbitmq import get_rabbitmq_rpc_client

from ...core.settings import ApplicationSettings
from ...services.service_tracker import get_tracked_service
from ._common import base_page
from ._utils import get_parent_app

router = APIRouter()


@router.page("/service/{node_id}:details")
async def service_details(node_id: NodeID):
    with base_page(title=f"{node_id} details"):
        service_model = await get_tracked_service(get_parent_app(app), node_id)

        if not service_model:
            ui.markdown(
                f"Sorry could not find any details for **node_id={node_id}**. "
                "Please make sure the **node_id** is correct. "
                "Also make sure you have not provided a **product_id**."
            )
            return

        scheduler_internals = service_model.model_dump(mode="json")
        service_status = json.loads(scheduler_internals.pop("service_status"))
        dynamic_service_start = scheduler_internals.pop("dynamic_service_start")

        ui.markdown("**Service Status**")
        ui.code(json.dumps(service_status, indent=2), language="json")

        ui.markdown("**Scheduler Internals**")
        ui.code(json.dumps(scheduler_internals, indent=2), language="json")

        ui.markdown("**Start Parameters**")
        ui.code(json.dumps(dynamic_service_start, indent=2), language="json")


@router.page("/service/{node_id}:stop")
async def service_stop(node_id: NodeID):
    with base_page(title=f"{node_id} details"):
        parent_app = get_parent_app(app)

        service_model = await get_tracked_service(parent_app, node_id)
        if not service_model:
            ui.notify(f"Could not stop service {node_id}. Was not abel to find it")
            return

        settings: ApplicationSettings = parent_app.state.settings

        assert service_model.user_id  #  nosec
        assert service_model.project_id  # nosec

        await stop_dynamic_service(
            get_rabbitmq_rpc_client(get_parent_app(app)),
            dynamic_service_stop=DynamicServiceStop(
                user_id=service_model.user_id,
                project_id=service_model.project_id,
                node_id=node_id,
                simcore_user_agent="",
                save_state=True,
            ),
            timeout_s=int(
                settings.DYNAMIC_SCHEDULER_STOP_SERVICE_TIMEOUT.total_seconds()
            ),
        )
