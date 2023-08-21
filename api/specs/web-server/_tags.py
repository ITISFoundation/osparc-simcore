# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from fastapi import APIRouter, status
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.tags._handlers import TagCreate, TagGet, TagUpdate

router = APIRouter(prefix=f"/{API_VTAG}", tags=["tags"])


@router.post(
    "/tags",
    response_model=Envelope[TagGet],
)
async def create_tag(create: TagCreate):
    ...


@router.get(
    "/tags",
    response_model=Envelope[list[TagGet]],
)
async def list_tags():
    ...


@router.patch(
    "/tags/{tag_id}",
    response_model=Envelope[TagGet],
)
async def update_tag(tag_id: int, update: TagUpdate):
    ...


@router.delete(
    "/tags/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_tag(tag_id: int):
    ...
