from typing import Optional

from fastapi import Depends, Query
from models_library.users import UserID

from ...db.repositories.groups import GroupsRepository
from ...models.domain.group import GroupAtDB
from .database import get_repository


async def list_user_groups(
    user_id: Optional[UserID] = Query(
        default=None,
        description="if passed, and that user has custom resources, "
        "they will be merged with default resources and returned.",
    ),
    groups_repository: GroupsRepository = Depends(get_repository(GroupsRepository)),
) -> list[GroupAtDB]:
    return await groups_repository.list_user_groups(user_id) if user_id else []
