""" Helper script to generate OAS automatically
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from enum import Enum

from fastapi import FastAPI
from models_library.generics import Envelope
from simcore_service_webserver.announcements._handlers import Announcement

app = FastAPI(redoc_url=None)

TAGS: list[str | Enum] = [
    "announcements",
]


@app.get(
    "/announcements",
    response_model=Envelope[list[Announcement]],
    tags=TAGS,
    operation_id="list_announcements",
)
async def list_announcements():
    ...


if __name__ == "__main__":
    from _common import CURRENT_DIR, create_openapi_specs

    create_openapi_specs(app, CURRENT_DIR.parent / "openapi-announcements.yaml")
