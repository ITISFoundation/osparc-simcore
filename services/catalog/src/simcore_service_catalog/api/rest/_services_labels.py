import urllib.parse
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends
from models_library.generics import Envelope
from models_library.services import ServiceKey, ServiceVersion

from ...services.director import DirectorApi
from ..dependencies.director import get_director_api

router = APIRouter()


@router.get("/{service_key:path}/{service_version}/labels")
async def get_service_labels(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    director_client: Annotated[DirectorApi, Depends(get_director_api)],
) -> Envelope[dict[str, Any]]:  # TODO: change the type
    response = await director_client.get(
        f"/services/{urllib.parse.quote_plus(service_key)}/{service_version}/labels"
    )
    # TODO: remove the envelope since it does not make sense
    return Envelope[dict[str, Any]](data=cast(dict[str, Any], response))
