import hashlib
from typing import List, Optional

import sqlalchemy as sa
from aiopg.sa.result import RowProxy

from ...models.schemas.profiles import Profile
from ..tables import GroupType, api_keys, groups, user_to_groups, users
from .base import BaseRepository


class UsersRepository(BaseRepository):
    async def get_user_id(self, api_key: str, api_secret: str) -> Optional[int]:
        stmt = sa.select([api_keys.c.user_id,]).where(
            sa.and_(api_keys.c.api_key == api_key, api_keys.c.api_secret == api_secret,)
        )
        user_id: Optional[int] = await self.connection.scalar(stmt)
        return user_id

    async def any_user_with_id(self, user_id: int) -> bool:
        # FIXME: shall identify api_key or api_secret instead
        stmt = sa.select([api_keys.c.user_id,]).where(api_keys.c.user_id == user_id)
        return (await self.connection.scalar(stmt)) is not None

    async def get_email_from_user_id(self, user_id: int) -> Optional[str]:
        stmt = sa.select([users.c.email,]).where(users.c.id == user_id)
        email: Optional[str] = await self.connection.scalar(stmt)
        return email

    # TEMPORARY ----
    async def get_profile_from_userid(self, user_id: int) -> Optional[Profile]:
        stmt = (
            sa.select(
                [
                    users.c.email,
                    users.c.role,
                    users.c.name,
                    users.c.primary_gid,
                    groups.c.gid,
                    groups.c.name,
                    groups.c.description,
                    groups.c.type,
                ],
                use_labels=True,
            )
            .select_from(
                users.join(
                    user_to_groups.join(groups, user_to_groups.c.gid == groups.c.gid),
                    users.c.id == user_to_groups.c.uid,
                )
            )
            .where(users.c.id == user_id)
            .order_by(sa.asc(groups.c.name))
        )

        # all user_group combinations but only the group changes
        result = await self.connection.execute(stmt)
        user_groups: List[RowProxy] = await result.fetchall()

        if not user_groups:
            return None

        # get the primary group and the all group
        user_primary_group = all_group = {}
        other_groups = []
        for user_group in user_groups:
            if user_group["users_primary_gid"] == user_group["groups_gid"]:
                user_primary_group = user_group
            elif user_group["groups_type"] == GroupType.EVERYONE:
                all_group = user_group
            else:
                other_groups.append(user_group)

        parts = user_primary_group["users_name"].split(".") + [""]
        return Profile.parse_obj(
            {
                "login": user_primary_group["users_email"],
                "first_name": parts[0],
                "last_name": parts[1],
                "role": user_primary_group["users_role"].name.capitalize(),
                "gravatar_id": gravatar_hash(user_primary_group["users_email"]),
                "groups": {
                    "me": {
                        "gid": user_primary_group["groups_gid"],
                        "label": user_primary_group["groups_name"],
                        "description": user_primary_group["groups_description"],
                    },
                    "organizations": [
                        {
                            "gid": group["groups_gid"],
                            "label": group["groups_name"],
                            "description": group["groups_description"],
                        }
                        for group in other_groups
                    ],
                    "all": {
                        "gid": all_group["groups_gid"],
                        "label": all_group["groups_name"],
                        "description": all_group["groups_description"],
                    },
                },
            }
        )


def gravatar_hash(email: str) -> str:
    return hashlib.md5(email.lower().encode("utf-8")).hexdigest()  # nosec
