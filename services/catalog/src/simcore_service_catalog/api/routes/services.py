import logging
from typing import List

from fastapi import APIRouter, Depends
from pydantic import ValidationError

from simcore_service_catalog.api.dependencies.director import get_director_session

from ...models.schemas.service import ServiceOut
from ..dependencies.director import AuthSession

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", response_model=List[ServiceOut])
async def list_services(client: AuthSession = Depends(get_director_session)):
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
