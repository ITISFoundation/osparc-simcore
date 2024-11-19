import asyncio
from collections.abc import AsyncIterable
from typing import Annotated, Final

from fastapi import APIRouter, Depends, FastAPI
from fastapi.responses import StreamingResponse
from fastui import AnyComponent, FastUI
from fastui import components as c
from fastui.events import PageEvent
from starlette import status

from ..dependencies import get_app
from ._constants import API_ROOT_PATH

_PREFIX: Final[str] = "/services"

router = APIRouter()


# root entrypoint for the application
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


# SSE endpoint
@router.get(f"{API_ROOT_PATH}{_PREFIX}/sse/")
async def sse_ai_response(
    app: Annotated[FastAPI, Depends(get_app)]
) -> StreamingResponse:
    return StreamingResponse(_render_messages(app), media_type="text/event-stream")


async def _render_messages(app: FastAPI) -> AsyncIterable[str]:
    _ = app  # TODO: fetch storage and render content from here
    messages: list[AnyComponent] = []
    # Avoid the browser reconnecting
    while True:
        # TODO: yield only if content changed, store a hash of the messages
        messages.append(c.Markdown(text="# LOL \n this is it!"))
        await asyncio.sleep(3)
        message = FastUI(root=messages)
        yield f"data: {message.model_dump_json(by_alias=True, exclude_none=True)}\n\n"


@router.get("/{path:path}", status_code=status.HTTP_404_NOT_FOUND)
async def not_found():
    return {"message": "Not Found"}
