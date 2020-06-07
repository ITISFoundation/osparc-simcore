from typing import Optional

import sqlalchemy as sa
from aiopg.sa.engine import Engine
from aiopg.sa.result import ResultProxy, RowProxy

import simcore_api_gateway.model.pg_tables as tbl
from simcore_api_gateway.schemas import UserInDB


async def test_row_proxy_into_model(engine: Engine):
    # test how RowProxy converts into into UserInDB

    with engine.acquire() as conn:
        stmt = sa.select([tbl.users,]).where(tbl.users.c.id == 1)

        res: ResultProxy = await conn.execute(stmt)
        row: Optional[RowProxy] = await res.fetchone()

    user = UserInDB.from_orm(row)
    assert user
