import logging
from typing import List

from fastapi import APIRouter, Depends
from pydantic import ValidationError

from ...db.repositories.services import ServicesRepository
from ...models.schemas.service import ServiceOut
from ...db.repositories.groups import GroupsRepository
from ..dependencies.database import get_repository
from ..dependencies.director import AuthSession, get_director_session

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", response_model=List[ServiceOut])
async def list_services(
    user_id: int,
    client: AuthSession = Depends(get_director_session),
    groups_repository: GroupsRepository = Depends(get_repository(GroupsRepository)),
    services_repo: ServicesRepository = Depends(get_repository(ServicesRepository)),
):
    # get all groups
    list_of_groups = await groups_repository.list_user_groups(user_id)
    logger.debug(
        "List of user group gids: %s",
        [f"{group.gid}:{group.name}" for group in list_of_groups],
    )
    # now get the allowed services
    list_of_allowed_services = await services_repo.list_services(
        gids=[group.gid for group in list_of_groups]
    )
    logger.debug("Allowed services: %s", list_of_allowed_services)
    allowed_services = {
        f"{service.key}:{service.version}"
        for service in list_of_allowed_services
        if service.execute_access
    }
    logger.debug("Allowed services: %s", allowed_services)
    data = await client.get("/services")
    services: List[ServiceOut] = []
    for x in data:
        try:
            service = ServiceOut.parse_obj(x)
            if f"{service.key}:{service.version}" in allowed_services:
                services.append(service)
        # services = parse_obj_as(List[ServiceOut], data)
        except ValidationError as exc:
            logger.warning(
                "skip service %s:%s that has invalid fields\n%s",
                x["key"],
                x["version"],
                exc,
            )

    return services
