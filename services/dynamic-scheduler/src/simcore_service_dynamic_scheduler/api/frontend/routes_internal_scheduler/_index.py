from nicegui import APIRouter, ui

from .._render_utils import base_page

router = APIRouter()


@router.page("/")
async def index():
    with base_page():
        ui.label("PLACEHOLDER for internal scheduler UI")
