import json

import httpx
from models_library.projects_nodes_io import NodeID
from nicegui import APIRouter, app, ui
from servicelib.rabbitmq.rpc_interfaces.dynamic_scheduler.services import (
    DynamicServiceStop,
    stop_dynamic_service,
)
from settings_library.utils_service import DEFAULT_FASTAPI_PORT
from simcore_service_dynamic_scheduler.services.rabbitmq import get_rabbitmq_rpc_client

from ....core.settings import ApplicationSettings
from ....services.service_tracker import get_tracked_service, remove_tracked_service
from .._utils import get_parent_app
from ._rendeer_utils import base_page

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

        ui.markdown("**Raw serialized data (the one used to render the above**")
        ui.code(service_model.model_dump_json(indent=2), language="json")

        ui.separator()

        ui.markdown(
            "**Dangerous Zone, beware!**\nThese actions can damage the system!"
        ).classes("text-red-700")

        with ui.dialog() as confirm_dialog, ui.card():

            async def remove_from_tracking():
                confirm_dialog.submit("Yes")
                await httpx.AsyncClient(timeout=10).get(
                    f"http://localhost:{DEFAULT_FASTAPI_PORT}/service/{node_id}/tracker:remove"
                )

                ui.notify(f"Removal request for {node_id} accepted")
                ui.navigate.to("/")

            ui.markdown(f"Remove from tracking **{node_id}**?")
            ui.label(
                "This will break the fronted for the user! They will no longer receive status updated!"
            ).classes("text-red-600")
            ui.label(
                "You want to do this if for whatever reason the dynamic-scheduler does not remove this item."
            )
            with ui.row():
                ui.button("Yes", color="red", on_click=remove_from_tracking)
                ui.button("No", on_click=lambda: confirm_dialog.submit("No"))

        async def display_confirm_dialog():
            await confirm_dialog

        ui.button(
            "Remove from tracking",
            icon="delete",
            color="red",
            on_click=display_confirm_dialog,
        ).tooltip("Removes the service form the dynamic-scheduler's internal tracking")


@router.page("/service/{node_id}:stop")
async def service_stop(node_id: NodeID):
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
        timeout_s=int(settings.DYNAMIC_SCHEDULER_STOP_SERVICE_TIMEOUT.total_seconds()),
    )


@router.page("/service/{node_id}/tracker:remove")
async def remove_service_from_tracking(node_id: NodeID):
    await remove_tracked_service(get_parent_app(app), node_id)
