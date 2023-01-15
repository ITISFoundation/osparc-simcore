""" Helper script to generate OAS automatically
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from enum import Enum
from typing import Union

from fastapi import FastAPI, status
from models_library.generics import Envelope
from simcore_service_webserver.tags_handlers import TagCreate, TagGet, TagUpdate

app = FastAPI(redoc_url=None)

TAGS: list[Union[str, Enum]] = [
    "tag",
]


@app.get(
    "/tags",
    response_model=Envelope[TagGet],
    tags=TAGS,
    operation_id="create_tag",
)
async def create_tag(create: TagCreate):
    ...


@app.get(
    "/tags",
    response_model=Envelope[list[TagGet]],
    tags=TAGS,
    operation_id="list_tags",
)
async def list_tags():
    ...


@app.patch(
    "/tags/{tag_id}",
    response_model=Envelope[TagGet],
    tags=TAGS,
    operation_id="update_tag",
)
async def update_tag(update: TagUpdate):
    ...


@app.delete(
    "/tags/{tag_id}",
    tags=TAGS,
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_tag",
)
async def delete_tag():
    ...


if __name__ == "__main__":

    from _common import CURRENT_DIR, create_openapi_specs

    create_openapi_specs(app, CURRENT_DIR.parent / "openapi-tags.yaml")
