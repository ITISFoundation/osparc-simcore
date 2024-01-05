import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.result import ResultProxy
from servicelib.aiohttp.aiopg_utils import PostgresRetryPolicyUponOperation
from tenacity import retry

from ..db.models import UserStatus, users
from ._identity import IdentityStr


@retry(
    **PostgresRetryPolicyUponOperation(_logger).kwargs
)  # TODO: move this to the _db part, not here
async def get_active_user(
    app: web.Application, email: IdentityStr
) -> _UserInfoDict | None:
    # NOTE: Keeps a cache for a few seconds. Observed successive streams of this query
    async with self.engine.acquire() as conn:
        # NOTE: sometimes it raises psycopg2.DatabaseError in #880 and #1160
        result: ResultProxy = await conn.execute(
            sa.select(users.c.id, users.c.role).where(
                (users.c.email == email) & (users.c.status == UserStatus.ACTIVE)
            )
        )
        row = await result.fetchone()
        return row
