# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Annotated

from fastapi import APIRouter, Depends
from models_library.api_schemas_webserver.projects import ProjectGet
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.catalog._handlers import ServicePathParams

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "catalog",
        "tags",
    ],
)


@router.put(
    "/catalog/services/{service_key}/{service_version}/tags/{tag_id}",
    response_model=Envelope[ProjectGet],
)
def add_service_tag(
    _path_params: Annotated[ServicePathParams, Depends()],
    tag_id: int,
):
    """
    Adds a tag (needs access) to a service (need access)
    """


@router.delete(
    "/catalog/services/{service_key}/{service_version}/tags/{tag_id}",
    response_model=Envelope[ProjectGet],
)
def remove_service_tag(
    _path_params: Annotated[ServicePathParams, Depends()],
    tag_id: int,
):
    """
    Adds a tag (needs access) from a service (need access)
    """
