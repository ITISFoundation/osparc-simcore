import json
import logging
from asyncio import Task
from datetime import timedelta
from typing import Annotated, Final

from fastapi import APIRouter, Depends, FastAPI
from fastapi.responses import StreamingResponse
from fastui import AnyComponent, FastUI
from fastui import components as c
from fastui.events import PageEvent
from models_library.projects_nodes_io import NodeID
from servicelib.background_task import start_periodic_task, stop_periodic_task
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from servicelib.logging_utils import log_catch, log_context
from starlette import status

from ...services.service_tracker import TrackedServiceModel, get_all_tracked_services
from ..dependencies import get_app
from ._constants import API_ROOT_PATH
from ._sse_utils import (
    AbstractSSERenderer,
    render_items_on_change,
    update_renderer_items,
)

_logger = logging.getLogger(__name__)

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
    def get_component(item: tuple[NodeID, TrackedServiceModel]) -> AnyComponent:
        node_id, service_model = item
        mode_data = service_model.model_dump(mode="json")
        return c.Div(
            components=[
                c.Text(text=f"NodeID: {node_id}"),
                c.Code(text=json.dumps(mode_data, indent=2), language="json"),
            ]
        )


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


class ServicesStatusRetriever(SingletonInAppStateMixin):
    app_state_name: str = "services_status_retriever"

    def __init__(self, app: FastAPI, poll_interval: timedelta) -> None:
        self.app = app
        self.poll_interval = poll_interval

        self._task: Task | None = None

    async def _task_service_state_retrieval(self) -> None:
        with log_context(
            _logger, logging.DEBUG, "update SSE services renderers"
        ), log_catch(_logger, reraise=False):
            all_tracked_services = await get_all_tracked_services(self.app)
            items = list(sorted(all_tracked_services.items()))  # noqa: C413

            await update_renderer_items(
                self.app, renderer_type=ServicesSSERenderer, items=items
            )

    def startup(self) -> None:
        self._task = start_periodic_task(
            self._task_service_state_retrieval,
            interval=self.poll_interval,
            task_name="sse_periodic_status_poll",
        )

    async def shutdown(self) -> None:
        if self._task:
            await stop_periodic_task(self._task, timeout=5)


def setup_services(app: FastAPI) -> None:
    async def on_startup() -> None:
        status_retriever = ServicesStatusRetriever(
            app, poll_interval=timedelta(seconds=1)
        )
        status_retriever.set_to_app_state(app)
        status_retriever.startup()

    async def on_shutdown() -> None:
        await ServicesStatusRetriever.get_from_app_state(app).shutdown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
