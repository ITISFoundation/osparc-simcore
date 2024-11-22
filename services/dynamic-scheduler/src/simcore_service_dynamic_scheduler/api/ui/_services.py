import json
import logging
from asyncio import Task
from datetime import timedelta
from typing import Annotated, Any, Final

import arrow
from fastapi import APIRouter, Depends, FastAPI
from fastapi.responses import StreamingResponse
from fastui import AnyComponent, FastUI
from fastui import components as c
from fastui.events import GoToEvent, PageEvent
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStop,
)
from models_library.projects_nodes_io import NodeID
from servicelib.background_task import start_periodic_task, stop_periodic_task
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from servicelib.logging_utils import log_catch, log_context
from servicelib.rabbitmq.rpc_interfaces.dynamic_scheduler.services import (
    stop_dynamic_service,
)
from simcore_service_dynamic_scheduler.services.service_tracker._models import (
    SchedulerServiceState,
)
from starlette import status

from ...core.settings import ApplicationSettings
from ...services.rabbitmq import get_rabbitmq_rpc_client
from ...services.service_tracker import (
    TrackedServiceModel,
    get_all_tracked_services,
    get_tracked_service,
)
from ..dependencies import get_app
from . import _custom_components as cu
from ._constants import API_ROOT_PATH, UI_MOUNT_PREFIX
from ._sse_utils import (
    AbstractSSERenderer,
    render_items_on_change,
    update_renderer_items,
)

_logger = logging.getLogger(__name__)

_PREFIX: Final[str] = "/services"

router = APIRouter()


def _page_base(
    *components: AnyComponent, page_title: str | None = None
) -> list[AnyComponent]:
    display_title = (
        f"Dynamic Scheduler — {page_title}" if page_title else "Dynamic Scheduler"
    )
    return [
        c.PageTitle(text=display_title),
        c.Navbar(title="Dynamic Scheduler", title_event=GoToEvent(url="/")),
        c.Page(components=[*components]),
        c.Footer(extra_text="z43 <3 inside", links=[]),
    ]


def _get_index_page() -> list[AnyComponent]:
    return _page_base(
        c.Heading(text="Dynamic services status", level=4),
        c.Paragraph(text="List of all services currently tracked by the scheduler"),
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
        c.FireEvent(event=PageEvent(name="page-loaded")),
    )


@router.get(
    f"{API_ROOT_PATH}/", response_model=FastUI, response_model_exclude_none=True
)
def api_index() -> list[AnyComponent]:
    return _get_index_page()


@router.get(
    f"{API_ROOT_PATH}{_PREFIX}/details/",
    response_model=FastUI,
    response_model_exclude_none=True,
)
async def service_details(
    node_id: NodeID, app: Annotated[FastAPI, Depends(get_app)]
) -> list[AnyComponent]:
    service_model = await get_tracked_service(app, node_id)

    service_inspect: AnyComponent = c.Text(
        text=f"Could not find service for provided node_id={node_id}"
    )
    if service_model:
        code = service_model.model_dump(mode="json")
        service_inspect = c.Code(text=json.dumps(code, indent=2), language="json")

    return _page_base(
        c.Heading(text=f"Details for {node_id}", level=4),
        service_inspect,
        page_title=f"details for {node_id}",
    )


@router.post(
    f"{API_ROOT_PATH}{_PREFIX}/stop-service/",
    response_model=FastUI,
    response_model_exclude_none=True,
)
async def stop_service(
    node_id: NodeID, app: Annotated[FastAPI, Depends(get_app)]
) -> list[AnyComponent]:
    service_model = await get_tracked_service(app, node_id)

    if service_model and service_model.user_id and service_model.project_id:
        settings: ApplicationSettings = app.state.settings
        await stop_dynamic_service(
            get_rabbitmq_rpc_client(app),
            dynamic_service_stop=DynamicServiceStop(
                user_id=service_model.user_id,
                project_id=service_model.project_id,
                node_id=node_id,
                simcore_user_agent="",
                save_state=True,
            ),
            timeout_s=int(
                settings.DYNAMIC_SCHEDULER_STOP_SERVICE_TIMEOUT.total_seconds()
            ),
        )

    return _get_index_page()


# TODO: add a toast for displaying the status of the stop operation
# TODO: change logic since SSE is not working as expected. You can use it to detect changes in the model  -> then reload the page, which is useless
# TODO: add an endpoint to remove from tracking without using anything else


def _render_partial(
    node_id: NodeID, service_model: TrackedServiceModel
) -> AnyComponent:
    list_display: list[tuple[Any, Any]] = [
        ("NodeID", node_id),
        ("Service state", service_model.current_state),
        (
            "Last state change",
            arrow.get(service_model.last_state_change).isoformat(),
        ),
        ("Requested", service_model.requested_state),
        ("ProjectID", service_model.project_id),
        ("UserID", service_model.user_id),
    ]

    if service_model.dynamic_service_start:
        list_display.extend(
            [
                ("Service Key", service_model.dynamic_service_start.key),
                ("Service Version", service_model.dynamic_service_start.version),
                ("Product", service_model.dynamic_service_start.product_name),
            ]
        )
    components = [
        c.Text(text="PARTIAL"),
        cu.markdown_list_display(list_display),
        c.Button(
            text="Details",
            named_style="secondary",
            on_click=GoToEvent(url=f"{_PREFIX}/details/?node_id={node_id}"),
        ),
        c.Button(
            text="Stop Service",
            on_click=PageEvent(name="modal-prompt"),
            class_name="+ ms-2",
        ),
    ]

    return c.Div(components=components, class_name="border border-double")


def _render_full(node_id: NodeID, service_model: TrackedServiceModel) -> AnyComponent:
    list_display: list[tuple[Any, Any]] = [
        ("NodeID", node_id),
        ("Service state", service_model.current_state),
        (
            "Last state change",
            arrow.get(service_model.last_state_change).isoformat(),
        ),
        ("Requested", service_model.requested_state),
        ("ProjectID", service_model.project_id),
        ("UserID", service_model.user_id),
    ]

    if service_model.dynamic_service_start:
        list_display.extend(
            [
                ("Service Key", service_model.dynamic_service_start.key),
                ("Service Version", service_model.dynamic_service_start.version),
                ("Product", service_model.dynamic_service_start.product_name),
            ]
        )
    components = [
        c.Text(text="FULL_RENDERED"),
        cu.markdown_list_display(list_display),
        c.Button(
            text="Details",
            named_style="secondary",
            on_click=GoToEvent(url=f"{_PREFIX}/details/?node_id={node_id}"),
        ),
        c.Button(
            text="Stop Service",
            on_click=PageEvent(name="modal-prompt"),
            class_name="+ ms-2",
        ),
        c.Modal(
            title="Stop Service",
            body=[
                c.Paragraph(text=f"Are you sure you want to stop {node_id}?"),
                c.Form(
                    form_fields=[],
                    submit_url=f"{UI_MOUNT_PREFIX}{API_ROOT_PATH}{_PREFIX}/stop-service/?node_id={node_id}",
                    loading=[c.Spinner(text="Stopping...")],
                    footer=[],
                    submit_trigger=PageEvent(name="modal-form-submit"),
                ),
            ],
            footer=[
                c.Button(
                    text="Cancel",
                    named_style="secondary",
                    on_click=PageEvent(name="modal-prompt", clear=True),
                ),
                c.Button(text="Submit", on_click=PageEvent(name="modal-form-submit")),
            ],
            open_trigger=PageEvent(name="modal-prompt"),
        ),
    ]

    return c.Div(components=components, class_name="border border-dotted")


class ServicesSSERenderer(AbstractSSERenderer):
    @staticmethod
    def get_component(item: tuple[NodeID, TrackedServiceModel]) -> AnyComponent:
        node_id, service_model = item

        if service_model.current_state == SchedulerServiceState.RUNNING:
            return _render_full(node_id, service_model)

        return _render_partial(node_id, service_model)


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
            task_name="sse_services_status_retrieval_from_redis",
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
