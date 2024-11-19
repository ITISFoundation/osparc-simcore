from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from fastui import prebuilt_html


def get_index_router(prefix: str) -> APIRouter:
    router = APIRouter()

    @router.get("/{path:path}")
    async def landing_page() -> HTMLResponse:
        return HTMLResponse(
            prebuilt_html(title="Dynamic Scheduler", api_root_url=f"{prefix}/api")
        )

    return router
