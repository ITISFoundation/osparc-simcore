import logging
from typing import TypedDict

import sqlalchemy as sa
from aiopg.sa import Engine
from aiopg.sa.result import ResultProxy
from models_library.basic_types import IdInt
from pydantic import parse_obj_as
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
        assert row is None or parse_obj_as(IdInt, row.id) is not None  # nosec
        assert row is None or parse_obj_as(UserRole, row.role) is not None  # nosec

        return AuthInfoDict(id=row.id, role=row.role) if row else None


# FIXME: check if user has this group
