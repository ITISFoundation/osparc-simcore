from fastapi import APIRouter
from fastui import AnyComponent, FastUI
from fastui import components as c
from starlette import status

from ._constants import API_ROOT_PATH

router = APIRouter()


# root entrypoint for the application
@router.get(
    f"{API_ROOT_PATH}/", response_model=FastUI, response_model_exclude_none=True
)
def api_index() -> list[AnyComponent]:
    return [
        c.PageTitle(text="FastUI Chatbot"),
        c.Page(
            components=[
                # Header
                c.Heading(text="FastUI Chatbot"),
                c.Paragraph(
                    text="This is a simple chatbot built with FastUI and MistralAI."
                ),
            ],
        ),
        # Footer
        c.Footer(extra_text="Made with FastUI", links=[]),
    ]


@router.get("/{path:path}", status_code=status.HTTP_404_NOT_FOUND)
async def not_found():
    return {"message": "Not Found"}
