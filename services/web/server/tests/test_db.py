import pprint
import io
import logging

import sqlalchemy as sa

from server.db._db import (
    create_aiopg,
    dispose_aiopg
)
from server.db.model import (
    users
)

_LOGGER = logging.getLogger(__name__)

async def test_basic_db_workflow(postgres_service, app_testconfig):
    """
        create engine
        connect
        query
        check against expected
        disconnect
    """
    # pylint:disable=E1120

    output = io.StringIO()
    pprint.pprint(postgres_service, stream=output)
    _LOGGER.info(output)

    assert postgres_service == app_testconfig["postgres"]
    app = dict(config=app_testconfig)

    await create_aiopg(app)
    # creates new engine!

    assert "db_engine" in app
    engine = app["db_engine"]
    async with engine.acquire() as connection:
        where = sa.and_(users.c.is_superuser, sa.not_(users.c.disabled))
        query = users.count().where(where)
        ret = await connection.scalar(query)
        assert ret == 1

    await dispose_aiopg(app)
    assert engine.closed
