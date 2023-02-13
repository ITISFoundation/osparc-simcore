import sqlalchemy as sa
from models_library.products import ProductName
from models_library.users import UserID

from ..tables import groups_extra_properties, user_to_groups
from ._base import BaseRepository

PRODUCTS_WITH_INTERNET: set[ProductName] = {"s4llite"}


class GroupsExtraPropertiesRepository(BaseRepository):
    async def has_internet_access(
        self, user_id: UserID, product_name: ProductName
    ) -> bool:
        # NOTE: PRODUCTS_WITH_INTERNET should be pulled from some
        # different source in the database
        if product_name not in PRODUCTS_WITH_INTERNET:
            # by default all products have access to the internet
            # unless the product has internet limitations
            return True

        # check to see if the product internet access was granted via a group
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
