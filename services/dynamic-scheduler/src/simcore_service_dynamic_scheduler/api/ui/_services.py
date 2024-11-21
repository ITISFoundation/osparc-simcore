import asyncio
from typing import Annotated, Any, Final

from fastapi import APIRouter, Depends, FastAPI
from fastapi.responses import StreamingResponse
from fastui import AnyComponent, FastUI
from fastui import components as c
from fastui.events import PageEvent
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from starlette import status

from ..dependencies import get_app
from ._constants import API_ROOT_PATH
from ._sse_utils import AbstractSSERenderer, render_items_on_change, update_items

_PREFIX: Final[str] = "/services"

router = APIRouter()


@router.get(
    f"{API_ROOT_PATH}/", response_model=FastUI, response_model_exclude_none=True
)
def api_index() -> list[AnyComponent]:
    return [
        c.PageTitle(text="Dynamic Services status"),
        c.Page(
            components=[
                c.Heading(text="Dynamic services"),
                c.Paragraph(
                    text="List of all services currently tracked by the scheduler"
                ),
            ]
        ),
        c.Div(
            components=[
                c.ServerLoad(
                    path=f"{_PREFIX}/sse/",
                    sse=True,
                    load_trigger=PageEvent(name="page-loaded"),
                    components=[],
                )
            ]
        ),
        c.Footer(extra_text="z43 <3 inside", links=[]),
        c.FireEvent(event=PageEvent(name="page-loaded")),
    ]


class ServicesSSERenderer(AbstractSSERenderer):
    @staticmethod
    def get_component(item: Any) -> AnyComponent:
        return c.Paragraph(text=f"{item}")


@router.get(f"{API_ROOT_PATH}{_PREFIX}/sse/")
async def sse_ai_response(
    app: Annotated[FastAPI, Depends(get_app)]
) -> StreamingResponse:
    return StreamingResponse(
        render_items_on_change(app, renderer_type=ServicesSSERenderer),
        media_type="text/event-stream",
    )


@router.get("/{path:path}", status_code=status.HTTP_404_NOT_FOUND)
async def not_found():
    return {"message": "Not Found"}


class MockMessagesProvider(SingletonInAppStateMixin):
    app_state_name: str = "mock_messages_provider"

    def __init__(self, app: FastAPI) -> None:
        self.app = app
        self._task: asyncio.Task | None = None

    async def _publish_mock_data(self) -> None:
        messages: list[Any] = []
        while True:
            await asyncio.sleep(3)

            messages.append({"name": "a", "surname": "b"})
            await update_items(
                self.app, renderer_type=ServicesSSERenderer, items=messages
            )

    def startup(self) -> None:
        self._task = asyncio.create_task(self._publish_mock_data())

    async def shutdown(self) -> None:
        if self._task:
            self._task.cancel()
            await self._task


def setup_services(app: FastAPI) -> None:
    async def on_startup() -> None:
        MockMessagesProvider.get_from_app_state(app).startup()

    async def on_shutdown() -> None:
        await MockMessagesProvider.get_from_app_state(app).shutdown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
