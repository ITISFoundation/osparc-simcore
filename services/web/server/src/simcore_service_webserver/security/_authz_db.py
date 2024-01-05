import logging
from typing import TypedDict

import sqlalchemy as sa
from aiopg.sa import Engine
from aiopg.sa.result import ResultProxy
from models_library.basic_types import IdInt
from pydantic import parse_obj_as
from servicelib.aiohttp.aiopg_utils import PostgresRetryPolicyUponOperation
from simcore_postgres_database.models.users import UserRole
from tenacity import retry

from ..db.models import UserStatus, users
from ._identity import IdentityStr

_logger = logging.getLogger(__name__)


class UserInfoDict(TypedDict, total=True):
    id: IdInt
    role: UserRole


@retry(**PostgresRetryPolicyUponOperation(_logger).kwargs)
async def get_active_user_or_none(
    engine: Engine, email: IdentityStr
) -> UserInfoDict | None:
    """Gets a user with email if ACTIVE othewise None

    Raises:
        HTTPServiceUnavailable: after pg retries fail
    """
    # NOTE: sometimes it raises psycopg2.DatabaseError in #880 and #1160

    async with engine.acquire() as conn:
        result: ResultProxy = await conn.execute(
            sa.select(users.c.id, users.c.role).where(
                (users.c.email == email) & (users.c.status == UserStatus.ACTIVE)
            )
        )
        row = await result.fetchone()
        assert row is None or parse_obj_as(IdInt, row.id) is not None  # nosec
        assert row is None or parse_obj_as(UserRole, row.role) is not None  # nosec

        return UserInfoDict(id=row.id, role=row.role) if row else None
