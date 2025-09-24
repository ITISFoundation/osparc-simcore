from nicegui import APIRouter

from . import _index, _service

router = APIRouter()

router.include_router(_index.router)
router.include_router(_service.router)

__all__: tuple[str, ...] = ("router",)
