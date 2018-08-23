import logging

import sqlalchemy as sa

from server.main import init_app
from server.settings import (
    read_and_validate
)

from server.db._db import (
    create_aiopg,
    dispose_aiopg
)
from server.db.model import (
    users
)


_LOGGER = logging.getLogger(__name__)

async def test_basic_db_workflow(mock_services, server_test_file):
    """
        create engine
        connect
        query
        check against expected
        disconnect
    """
    _LOGGER.debug("Started %s", mock_services)

    # init app from config file
    config = read_and_validate( server_test_file )
    app = init_app(config)

    # emulates app startup (see app.on_startup in setup_db)
    await create_aiopg(app)

    assert "db_engine" in app
    engine = app["db_engine"]

    # pylint: disable=E1111, E1120
    async with engine.acquire() as connection:
        where = sa.and_(users.c.is_superuser, sa.not_(users.c.disabled))
        query = users.count().where(where)
        ret = await connection.scalar(query)
        assert ret == 1

    await dispose_aiopg(app)
    assert engine.closed
