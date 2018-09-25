import logging

import sqlalchemy as sa

from simcore_service_webserver.main import init_app
from simcore_service_webserver.settings import (
    read_and_validate
)

from simcore_service_webserver.db.core import (
    create_aiopg,
    dispose_aiopg,
    APP_ENGINE_KEY
)
from simcore_service_webserver.db.model import (
    users
)


log = logging.getLogger(__name__)

async def test_basic_db_workflow(mock_services, server_test_configfile):
    """
        create engine
        connect
        query
        check against expected
        disconnect
    """
    log.debug("Started %s", mock_services)

    # init app from config file
    config = read_and_validate( server_test_configfile )
    app = init_app(config)

    # emulates app startup (see app.on_startup in setup_db)
    await create_aiopg(app)

    assert APP_ENGINE_KEY in app
    engine = app[APP_ENGINE_KEY]

    # pylint: disable=E1111, E1120
    async with engine.acquire() as connection:
        where = sa.and_(users.c.is_superuser, sa.not_(users.c.disabled))
        query = users.count().where(where)
        ret = await connection.scalar(query)
        assert ret == 1

    await dispose_aiopg(app)
    assert engine.closed
