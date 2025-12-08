from nicegui import APIRouter, ui

router = APIRouter()


@router.page("/")
async def index():
    ui.label("PLACEHOLDER for internal scheduler UI")
