import sqlalchemy as sa
from models_library.products import ProductName
from models_library.users import UserID

from ..tables import groups_extra_properties, user_to_groups
from ._base import BaseRepository


class GroupsExtraPropertiesRepository(BaseRepository):
    async def has_internet_access(
        self, user_id: UserID, product_name: ProductName
    ) -> bool:
        # NOTE: except the product below all others
        # always HAVE internet access
        # NOTE: this issue needs be addressed ASAP
        # https://github.com/ITISFoundation/osparc-simcore/issues/3875
        if product_name != "s4llite":
            return True

        async with self.db_engine.acquire() as conn:
            # checks if one of the groups which the user is part of has internet access
            select_stmt = sa.select(
                [groups_extra_properties.c.internet_access]
            ).select_from(
                user_to_groups.join(
                    groups_extra_properties,
                    (groups_extra_properties.c.group_id == user_to_groups.c.gid)
                    & (user_to_groups.c.uid == user_id)
                    & (groups_extra_properties.c.internet_access == True),
                )
            )

            user_with_access = await conn.scalar(select_stmt)
            return user_with_access is not None
