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

from typing import Set, Tuple


@router.get("", response_model=List[ServiceOut])
async def list_services(
    user_id: int,
    client: AuthSession = Depends(get_director_session),
    groups_repository: GroupsRepository = Depends(get_repository(GroupsRepository)),
    services_repo: ServicesRepository = Depends(get_repository(ServicesRepository)),
):
    # get user groups
    user_groups = await groups_repository.list_user_groups(user_id)
    # now get the allowed services
    allowed_services: Set[Tuple[str, str]] = {
        (service.key, service.version)
        for service in await services_repo.list_services(
            gids=[group.gid for group in user_groups]
        )
        if service.execute_access
    }

    # get the services from the registry
    data = await client.get("/services")
    services: List[ServiceOut] = []
    for x in data:
        try:
            service = ServiceOut.parse_obj(x)
            if (service.key, service.version) in allowed_services:
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
