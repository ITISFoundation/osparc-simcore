from typing import Annotated

from fastapi import Depends, Query
from models_library.groups import GroupAtDB
from models_library.users import UserID

from ...repositories.groups import GroupsRepository
from .database import get_repository


async def list_user_groups(
    groups_repository: Annotated[
        GroupsRepository, Depends(get_repository(GroupsRepository))
    ],
    user_id: Annotated[
        UserID | None,
        Query(
            description="if passed, and that user has custom resources, "
            "they will be merged with default resources and returned.",
        ),
    ] = None,
) -> list[GroupAtDB]:
    return await groups_repository.list_user_groups(user_id) if user_id else []
