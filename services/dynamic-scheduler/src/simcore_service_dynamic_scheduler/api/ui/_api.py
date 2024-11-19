import asyncio
from typing import AsyncIterable

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from fastui import AnyComponent, FastUI
from fastui import components as c
from fastui.events import PageEvent
from starlette import status

from ._constants import API_ROOT_PATH

router = APIRouter()

# Add an event provider and then display stuff from there that changes


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
                    path="/sse/",
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
@router.get(f"{API_ROOT_PATH}/sse/")
async def sse_ai_response() -> StreamingResponse:
    return StreamingResponse(_render_messages(), media_type="text/event-stream")


async def _render_messages() -> AsyncIterable[str]:
    messages: list[AnyComponent] = []
    # Avoid the browser reconnecting
    while True:
        messages.append(c.Markdown(text="# LOL \n this is it!"))
        await asyncio.sleep(3)
        message = FastUI(root=messages)
        yield f"data: {message.model_dump_json(by_alias=True, exclude_none=True)}\n\n"


@router.get("/{path:path}", status_code=status.HTTP_404_NOT_FOUND)
async def not_found():
    return {"message": "Not Found"}
