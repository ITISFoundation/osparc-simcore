import json

import arrow
import httpx
from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from nicegui import APIRouter, app, ui
from nicegui.element import Element
from settings_library.utils_service import DEFAULT_FASTAPI_PORT

from ...services.service_tracker import TrackedServiceModel, get_all_tracked_services
from ...services.service_tracker._models import SchedulerServiceState
from ._common import base_page
from ._utils import get_parent_app

router = APIRouter()


def _get_elapsed(timestamp: float) -> str:
    elapsed_time = arrow.utcnow() - arrow.get(timestamp)

    days = elapsed_time.days
    hours, remainder = divmod(elapsed_time.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    # Format as "days hours:minutes:seconds"
    return f"{days} days, {hours:02}:{minutes:02}:{seconds:02} ago"


def _render_service_details(node_id: NodeID, service: TrackedServiceModel) -> None:
    dict_to_render: dict[str, tuple[str, str]] = {
        "NodeID": ("code", f"{node_id}"),
        "Display State": ("label", service.current_state),
        "Last State Change": ("label", _get_elapsed(service.last_state_change)),
        "UserID": ("code", f"{service.user_id}"),
        "ProjectID": ("code", f"{service.project_id}"),
        "User Requested": ("label", service.requested_state),
    }

    if service.dynamic_service_start:
        dict_to_render["Service"] = (
            "label",
            f"{service.dynamic_service_start.key}:{service.dynamic_service_start.version}",
        )
        dict_to_render["Product"] = (
            "label",
            service.dynamic_service_start.product_name,
        )
        service_status = json.loads(service.service_status) or {}
        dict_to_render["Service State"] = (
            "label",
            service_status.get("service_state", ""),
        )

    with ui.column().classes("p-0 m-0"):
        for key, (widget, value) in dict_to_render.items():
            with ui.row(align_items="baseline").classes("p-0 m-0"):
                ui.label(key).classes("font-bold")
                match widget:
                    case "code":
                        ui.code(value)
                    case "label":
                        ui.label(value)
                    case _:
                        ui.label(value)


def _render_buttons(node_id: NodeID, service: TrackedServiceModel) -> None:
    with ui.row(align_items="baseline").classes("p-0 m-0"):
        ui.button(
            "Details",
            icon="source",
            on_click=lambda: ui.navigate.to(f"/service/{node_id}:details"),
        )

        def _render_progress() -> None:
            ui.spinner(size="lg")

        storage_key = f"removing-{node_id}"
        if app.storage.general.get(storage_key, None):
            # removal is in progress just render progress bar
            _render_progress()
            return

        if service.current_state == SchedulerServiceState.RUNNING:
            with ui.row(align_items="baseline").classes("p-0 m-0") as container:

                async def async_task():
                    container.clear()

                    _render_progress()
                    app.storage.general[storage_key] = True

                    ui.notify(f"Started service stop request for {node_id}")

                    await httpx.AsyncClient(timeout=10).get(
                        f"http://localhost:{DEFAULT_FASTAPI_PORT}/service/{node_id}:stop"
                    )

                    app.storage.general.pop("removing-{node_id}", None)
                    ui.notify(f"Finished service stop request for {node_id}")

                ui.button("Stop service", icon="stop", on_click=async_task)


def _render_card(
    card_container: Element, node_id: NodeID, service: TrackedServiceModel
) -> None:
    with card_container:  # noqa: SIM117
        with ui.column().classes("border p-0 m-0"):
            _render_service_details(node_id, service)
            _render_buttons(node_id, service)


class CardUpdater:
    def __init__(self, parent_app: FastAPI, container: Element) -> None:
        self.parent_app = parent_app
        self.container = container

    async def update(self) -> None:
        # TODO: rerender only if data changed

        self.container.clear()  # Clear the current cards

        tracked_services = await get_all_tracked_services(self.parent_app)

        for node_id, service in tracked_services.items():
            _render_card(self.container, node_id, service)


@router.page("/")
async def index():
    with base_page():

        # Initial UI setup
        ui.label("Dynamic Item List")

        card_container: Element = ui.row()

        updater = CardUpdater(get_parent_app(app), card_container)

        # render cards when page is loaded
        await updater.update()
        # update card at a set interval
        ui.timer(1, lambda: updater.update())
