""" Helper script to generate OAS automatically
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from fastapi import APIRouter, FastAPI, status
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.tags._handlers import TagCreate, TagGet, TagUpdate

router = APIRouter(prefix=f"/{API_VTAG}", tags=["tags"])


@router.post(
    "/tags",
    response_model=Envelope[TagGet],
    operation_id="create_tag",
)
async def create_tag(create: TagCreate):
    ...


@router.get(
    "/tags",
    response_model=Envelope[list[TagGet]],
    operation_id="list_tags",
)
async def list_tags():
    ...


@router.patch(
    "/tags/{tag_id}",
    response_model=Envelope[TagGet],
    operation_id="update_tag",
)
async def update_tag(tag_id: int, update: TagUpdate):
    ...


@router.delete(
    "/tags/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_tag",
)
async def delete_tag(tag_id: int):
    ...


if __name__ == "__main__":
    from _common import CURRENT_DIR, create_and_save_openapi_specs

    create_and_save_openapi_specs(
        FastAPI(routes=router.routes), CURRENT_DIR.parent / "openapi-tags.yaml"
    )
