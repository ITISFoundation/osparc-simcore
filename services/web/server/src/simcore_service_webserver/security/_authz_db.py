import logging
from typing import TypedDict

import sqlalchemy as sa
from aiopg.sa import Engine
from aiopg.sa.result import ResultProxy
from models_library.basic_types import IdInt
from models_library.products import ProductName
from models_library.users import UserID
from pydantic import TypeAdapter
from simcore_postgres_database.models.groups import user_to_groups
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.users import UserRole

from ..db.models import UserStatus, users

_logger = logging.getLogger(__name__)


class AuthInfoDict(TypedDict, total=True):
    id: IdInt
    role: UserRole


async def get_active_user_or_none(engine: Engine, email: str) -> AuthInfoDict | None:
    """Gets a user with email if ACTIVE othewise return None

    Raises:
        DatabaseError: unexpected errors found in https://github.com/ITISFoundation/osparc-simcore/issues/880 and https://github.com/ITISFoundation/osparc-simcore/pull/1160
    """
    async with engine.acquire() as conn:
        result: ResultProxy = await conn.execute(
            sa.select(users.c.id, users.c.role).where(
                (users.c.email == email) & (users.c.status == UserStatus.ACTIVE)
            )
        )
        row = await result.fetchone()
        assert (
            row is None or TypeAdapter(IdInt).validate_python(row.id) is not None   # nosec
        )
        assert (
            row is None or TypeAdapter(UserRole).validate_python(row.role) is not None  # nosec
        )

        return AuthInfoDict(id=row.id, role=row.role) if row else None


async def is_user_in_product_name(
    engine: Engine, user_id: UserID, product_name: ProductName
) -> bool:
    async with engine.acquire() as conn:
        return (
            await conn.scalar(
                sa.select(users.c.id)
                .select_from(
                    users.join(user_to_groups, user_to_groups.c.uid == users.c.id).join(
                        products, products.c.group_id == user_to_groups.c.gid
                    )
                )
                .where((users.c.id == user_id) & (products.c.name == product_name))
            )
            is not None
        )
