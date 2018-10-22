import logging

import pytest
import sqlalchemy as sa

from simcore_service_webserver.application import create_application
from simcore_service_webserver.application_keys import APP_DB_ENGINE_KEY
from simcore_service_webserver.db.core import (create_aiopg,
                                               dispose_aiopg)
from simcore_service_webserver.db.model import users
from simcore_service_webserver.cli_config import read_and_validate
from simcore_service_webserver.db.utils import (DNS, acquire_admin_engine,
                                                acquire_engine)

log = logging.getLogger(__name__)


def _is_db_service_responsive(**pg_config):
    try:
        admin_engine = acquire_admin_engine(**pg_config)
        conn = admin_engine.connect()
        conn.close()
    except:
        log.exception("Connection to db failed")
        return False
    return True


@pytest.fixture(scope="session")
def mock_services(docker_ip, docker_services, docker_compose_file, server_test_configfile):
    """
      services in mock/docker-compose.yml
    """

    with open(docker_compose_file) as stream:
        c = yaml.load(stream)
        for service_name in c["services"].keys():
            # pylint: disable=W0212
            docker_services._services.get(service_name, {})

    # Patches os.environ to influence
    pre_os_environ = os.environ.copy()
    os.environ["POSTGRES_PORT"] = str(
        docker_services.port_for('postgres', 5432))
    os.environ["RABBIT_HOST"] = str(docker_ip)

    # loads app config
    app_config = read_and_validate(server_test_configfile)
    pg_config = app_config["postgres"]

    # NOTE: this can be eventualy handled by the service under test as well!!
    docker_services.wait_until_responsive(
        check=lambda: _is_db_service_responsive(**pg_config),
        timeout=20.0,
        pause=1.0,
    )

    # start db & inject mockup data
    test_engine = acquire_engine(DNS.format(**pg_config))
    init_db.setup_db(pg_config)
    init_db.create_tables(test_engine)
    init_db.sample_data(test_engine)

    yield docker_services

    init_db.drop_tables(test_engine)
    init_db.teardown_db(pg_config)

    os.environ = pre_os_environ

    
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
    app = create_application(config)

    # emulates app startup (see app.on_startup in setup_db)
    await create_aiopg(app)

    assert APP_DB_ENGINE_KEY in app
    engine = app[APP_DB_ENGINE_KEY]

    # pylint: disable=E1111, E1120
    async with engine.acquire() as connection:
        where = sa.and_(users.c.is_superuser, sa.not_(users.c.disabled))
        query = users.count().where(where)
        ret = await connection.scalar(query)
        assert ret == 1

    await dispose_aiopg(app)
    assert engine.closed
