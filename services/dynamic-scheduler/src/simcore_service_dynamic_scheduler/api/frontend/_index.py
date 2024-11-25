from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from nicegui import APIRouter, app, ui
from nicegui.element import Element

from ...services.service_tracker import TrackedServiceModel, get_all_tracked_services
from ._common import base_page
from ._utils import get_parent_app

router = APIRouter()


def _render_card(
    card_container: Element, node_id: NodeID, service: TrackedServiceModel
) -> None:
    with card_container:  # noqa: SIM117
        with ui.card():
            ui.label(f"{node_id}")
            # TODO finish card
            ui.label(service.model_dump_json())


async def _update_cards(parent_app: FastAPI, card_container) -> None:
    card_container.clear()  # Clear the current cards

    tracked_services = await get_all_tracked_services(parent_app)

    for node_id, service in tracked_services.items():
        _render_card(card_container, node_id, service)


# changed this form ui to router
@router.page("/")
async def main_page():
    parent_app = get_parent_app(app)

    with base_page():

        # Initial UI setup
        ui.label("Dynamic Item List")

        card_container: Element = ui.row()

        # render cards when page is loaded
        await _update_cards(parent_app, card_container)

        # update card at a set interval
        ui.timer(1.0, lambda: _update_cards(parent_app, card_container))
