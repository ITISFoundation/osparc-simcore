from nicegui import APIRouter

from . import _index

router = APIRouter()

router.include_router(_index.router)

__all__: tuple[str, ...] = ("router",)
