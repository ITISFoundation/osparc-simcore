import json

import httpx
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStop,
)
from models_library.projects_nodes_io import NodeID
from nicegui import APIRouter, app, ui
from servicelib.rabbitmq.rpc_interfaces.dynamic_scheduler.services import (
    stop_dynamic_service,
)
from settings_library.utils_service import DEFAULT_FASTAPI_PORT
from simcore_service_dynamic_scheduler.services.rabbitmq import get_rabbitmq_rpc_client

from ....core.settings import ApplicationSettings
from ....services.service_tracker import get_tracked_service, remove_tracked_service
from .._utils import get_parent_app, get_settings
from ._render_utils import base_page

router = APIRouter()


def _render_remove_from_tracking(node_id):
    with ui.dialog() as confirm_dialog, ui.card():

        async def remove_from_tracking():
            confirm_dialog.close()

            url = f"http://localhost:{DEFAULT_FASTAPI_PORT}{get_settings().DYNAMIC_SCHEDULER_UI_MOUNT_PATH}service/{node_id}/tracker:remove"
            await httpx.AsyncClient(timeout=10).get(f"{url}")

            ui.notify(f"Service {node_id} removed from tracking")
            ui.navigate.to("/")

        ui.markdown(f"Remove the service **{node_id}** form the tracker?")
        ui.label(
            "This action will result in the removal of the service form the internal tracker. "
            "This action should be used whn you are facing issues and the service is not "
            "automatically removed."
        )
        ui.label(
            "NOTE 1: the system normally cleans up services but it might take a few minutes. "
            "Only use this option when you have observed enough time passing without any change."
        ).classes("text-red-600")
        ui.label(
            "NOTE 2: This will break the fronted for the user! If the user has the service opened, "
            "it will no longer receive an status updates."
        ).classes("text-red-600")

        with ui.row():
            ui.button("Remove service", color="red", on_click=remove_from_tracking)
            ui.button("Cancel", on_click=confirm_dialog.close)

    ui.button(
        "Remove from tracking",
        icon="remove_circle",
        color="red",
        on_click=confirm_dialog.open,
    ).tooltip("Removes the service form the dynamic-scheduler's internal tracking")


def _render_danger_zone(node_id: NodeID) -> None:
    ui.separator()

    ui.markdown("**Danger Zone, beware!**").classes("text-2xl text-red-700")
    ui.label(
        "Do not use these actions if you do not know what they are doing."
    ).classes("text-red-700")

    ui.label(
        "They are reserved as means of recovering the system form a failing state."
    ).classes("text-red-700")

    _render_remove_from_tracking(node_id)


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
        service_status = scheduler_internals.pop("service_status", "{}")
        service_status = json.loads("{}" if service_status == "" else service_status)
        dynamic_service_start = scheduler_internals.pop("dynamic_service_start")

        ui.markdown("**Service Status**")
        ui.code(json.dumps(service_status, indent=2), language="json")

        ui.markdown("**Scheduler Internals**")
        ui.code(json.dumps(scheduler_internals, indent=2), language="json")

        ui.markdown("**Start Parameters**")
        ui.code(json.dumps(dynamic_service_start, indent=2), language="json")

        ui.markdown("**Raw serialized data (the one used to render the above**")
        ui.code(service_model.model_dump_json(indent=2), language="json")

        _render_danger_zone(node_id)


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
    parent_app = get_parent_app(app)

    service_model = await get_tracked_service(parent_app, node_id)
    if not service_model:
        ui.notify(f"Could not remove service {node_id}. Was not abel to find it")
        return

    await remove_tracked_service(parent_app, node_id)
