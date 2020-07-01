import logging
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import ValidationError
from pydantic.tools import parse_obj_as
from starlette import status

from simcore_service_catalog.api.dependencies.director import get_director_session

from ...models.schemas.service import ServiceOut
from ..dependencies.director import AuthSession

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", response_model=List[ServiceOut])
async def list_services(
    client: AuthSession = Depends(get_director_session),
    page_token: Optional[str] = Query(
        None, description="Requests a specific page of the list results"
    ),
    page_size: int = Query(
        0, ge=0, description="Maximum number of results to be returned by the server"
    ),
    order_by: Optional[str] = Query(
        None, description="Sorts in ascending order comma-separated fields"
    ),
):
    data = await client.get("/services")
    services: List[ServiceOut] = []
    for x in data:
        try:
            services.append(ServiceOut.parse_obj(x))
        # services = parse_obj_as(List[ServiceOut], data)
        except ValidationError as exc:
            logger.warning(
                "skip service %s:%s that has invalid fields\n%s",
                x["key"],
                x["version"],
                exc,
            )

    return services
