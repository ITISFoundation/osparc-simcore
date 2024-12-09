import json

import httpx
from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from nicegui import APIRouter, app, ui
from nicegui.element import Element
from nicegui.elements.label import Label
from settings_library.utils_service import DEFAULT_FASTAPI_PORT

from ....services.service_tracker import TrackedServiceModel, get_all_tracked_services
from ....services.service_tracker._models import SchedulerServiceState
from .._utils import get_parent_app, get_settings
from ._render_utils import base_page, get_iso_formatted_date

router = APIRouter()


def _render_service_details(node_id: NodeID, service: TrackedServiceModel) -> None:
    dict_to_render: dict[str, tuple[str, str]] = {
        "NodeID": ("copy", f"{node_id}"),
        "Display State": ("label", service.current_state),
        "Last State Change": (
            "label",
            get_iso_formatted_date(service.last_state_change),
        ),
        "UserID": ("copy", f"{service.user_id}"),
        "ProjectID": ("copy", f"{service.project_id}"),
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
        service_status = (
            json.loads(service.service_status) if service.service_status else {}
        )
        dict_to_render["Service State"] = (
            "label",
            service_status.get(
                "state" if "boot_type" in service_status else "service_state", "N/A"
            ),
        )

    with ui.column().classes("gap-0"):
        for key, (widget, value) in dict_to_render.items():
            with ui.row(align_items="baseline"):
                ui.label(key).classes("font-bold")
                match widget:
                    case "copy":
                        ui.label(value).classes("border bg-slate-200 px-1")
                    case "label":
                        ui.label(value)
                    case _:
                        ui.label(value)


def _render_buttons(node_id: NodeID, service: TrackedServiceModel) -> None:

    with ui.dialog() as confirm_dialog, ui.card():
        ui.markdown(f"Stop service **{node_id}**?")
        ui.label("The service will be stopped and its data will be saved.")
        with ui.row():

            async def _stop_service() -> None:
                confirm_dialog.close()

                url = f"http://localhost:{DEFAULT_FASTAPI_PORT}{get_settings().DYNAMIC_SCHEDULER_UI_MOUNT_PATH}service/{node_id}:stop"
                await httpx.AsyncClient(timeout=10).get(f"{url}")

                ui.notify(
                    f"Submitted stop request for {node_id}. Please give the service some time to stop!"
                )

            ui.button("Stop Now", color="red", on_click=_stop_service)
            ui.button("Cancel", on_click=confirm_dialog.close)

    with ui.button_group():
        ui.button(
            "Details",
            icon="source",
            on_click=lambda: ui.navigate.to(f"/service/{node_id}:details"),
        ).tooltip("Display more information about what the scheduler is tracking")

        if service.current_state != SchedulerServiceState.RUNNING:
            return

        ui.button(
            "Stop Service",
            icon="stop",
            color="orange",
            on_click=confirm_dialog.open,
        ).tooltip("Stops the service and saves the data")


def _render_card(
    card_container: Element, node_id: NodeID, service: TrackedServiceModel
) -> None:
    with card_container:  # noqa: SIM117
        with ui.column().classes("border p-1"):
            _render_service_details(node_id, service)
            _render_buttons(node_id, service)


def _get_clean_hashable(model: TrackedServiceModel) -> dict:
    """removes items which trigger frequent updates and are not interesting to the user"""
    data = model.model_dump(mode="json")
    data.pop("check_status_after")
    data.pop("last_status_notification")
    data.pop("service_status_task_uid")
    return data


def _get_hash(items: list[tuple[NodeID, TrackedServiceModel]]) -> int:
    return hash(
        json.dumps([(f"{key}", _get_clean_hashable(model)) for key, model in items])
    )


class CardUpdater:
    def __init__(
        self, parent_app: FastAPI, container: Element, services_count_label: Label
    ) -> None:
        self.parent_app = parent_app
        self.container = container
        self.services_count_label = services_count_label
        self.last_hash: int = _get_hash([])

    async def update(self) -> None:
        tracked_services = await get_all_tracked_services(self.parent_app)
        tracked_items: list[tuple[NodeID, TrackedServiceModel]] = sorted(
            tracked_services.items(), reverse=True
        )

        current_hash = _get_hash(tracked_items)

        if self.last_hash != current_hash:
            self.services_count_label.set_text(f"{len(tracked_services)}")
            # Clear the current cards
            self.container.clear()
            for node_id, service in tracked_items:
                _render_card(self.container, node_id, service)

        self.last_hash = current_hash


@router.page("/")
async def index():
    with base_page():
        with ui.row().classes("gap-0"):
            ui.label("Total tracked services:")
            ui.label("").classes("w-1")
            with ui.label("0") as services_count_label:
                pass

        card_container: Element = ui.row()

        updater = CardUpdater(get_parent_app(app), card_container, services_count_label)

        # render cards when page is loaded
        await updater.update()
        # update card at a set interval
        ui.timer(1, updater.update)
