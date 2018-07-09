import pprint
import io
import logging

import pytest
import sqlalchemy as sa

from server.config import get_config, SRC_DIR
from server.db import (
    create_aiopg,
    dispose_aiopg
)
from server.model import (
    users
)

_LOGGER = logging.getLogger(__name__)

async def test_basic_db_workflow(postgres_service):
    """
        create engine
        connect
        query
        check against expected
        disconnect
    """
    output = io.StringIO()
    pprint.pprint(postgres_service, stream=output)
    _LOGGER.info(output)

    #TEST_CONFIG_PATH = SRC_DIR / ".config" / "server-test.yaml"
    #app = {"config": get_config(["-c", TEST_CONFIG_PATH.as_posix()])}
    app = dict(config=postgres_service)

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
