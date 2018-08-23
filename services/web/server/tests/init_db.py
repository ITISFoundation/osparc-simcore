""" Initializes tables in database and adds some sample data for testing

FIXME: this place does not fill right... see how this script is called
FIXME: check https://github.com/aio-libs/aiohttp_admin/blob/master/demos/blog/aiohttpdemo_blog/generate_data.py
FIXME: rename as server.dev.generate_data.py and set dev as an optional sub-package as server[dev]


Example of usage

    cd services/web/server/tests/mock
    docker-compose up

    cd ../../config
    python init_db.py

References:
[1]:https://github.com/aio-libs/aiohttp-demos/blob/master/docs/preparations.rst#environment
"""
import logging
import sys
import pathlib

from passlib.hash import sha256_crypt
from sqlalchemy import (
    MetaData,
)
from tenacity import (
    retry,
    stop_after_attempt,
    wait_fixed,
    before_sleep_log
)

from server.db.utils import (
    DNS,
    acquire_engine,
    acquire_admin_engine
)

from server.db.model import (
    permissions,
    users
)
from server.settings import (
    read_and_validate
)

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)

CURRENT_DIR = pathlib.Path(sys.argv[0] if __name__ == "__main__" else __file__).parent.absolute()


def load_pgconfig(config_path):
    config = read_and_validate(config_path.as_posix())
    pg_config = config["postgres"]
    return pg_config

def setup_db(pg_config):
    db_name = pg_config["database"]
    db_user = pg_config["user"]
    db_pass = pg_config["password"]

    # TODO: compose using query semantics. Clarify pros/cons vs string cli?
    admin_engine = acquire_admin_engine(**pg_config)
    conn = admin_engine.connect()
    conn.execute("DROP DATABASE IF EXISTS %s" % db_name)
    conn.execute("DROP ROLE IF EXISTS %s" % db_user)
    conn.execute("CREATE USER %s WITH PASSWORD '%s'" % (db_user, db_pass))
    conn.execute("CREATE DATABASE %s ENCODING 'UTF8'" % db_name)
    conn.execute("GRANT ALL PRIVILEGES ON DATABASE %s TO %s" %
                 (db_name, db_user))
    conn.close()


def teardown_db(config):
    db_name = config["database"]
    db_user = config["user"]

    admin_engine = acquire_admin_engine(**config)
    conn = admin_engine.connect()
    conn.execute("""
      SELECT pg_terminate_backend(pg_stat_activity.pid)
      FROM pg_stat_activity
      WHERE pg_stat_activity.datname = '%s'
        AND pid <> pg_backend_pid();""" % db_name)
    conn.execute("DROP DATABASE IF EXISTS %s" % db_name)
    conn.execute("DROP ROLE IF EXISTS %s" % db_user)
    conn.close()


def create_tables(engine):
    meta = MetaData()
    meta.create_all(bind=engine, tables=[users, permissions])


def drop_tables(engine):
    meta = MetaData()
    meta.drop_all(bind=engine, tables=[users, permissions])


def sample_data(engine):
    generate_password_hash = sha256_crypt.hash

    #TODO: use fake to populate database
    # pylint:disable=E1120
    conn = engine.connect()
    conn.execute(users.insert(), [
        {"login": "bizzy@itis.ethz.ch",
         "passwd": generate_password_hash("z43"),
         "is_superuser": False,
         "disabled": False},
        {"login": "pcrespov@foo.com",
         "passwd": generate_password_hash("123"),
         "is_superuser": True,
         "disabled": False},
        {"login": "mrspam@bar.io",
         "passwd": generate_password_hash("345"),
         "is_superuser": True,
         "disabled": True}
    ])

    conn.execute(permissions.insert(), [
        {"user_id": 1,
         "perm_name": "tester"},
        {"user_id": 2,
         "perm_name": "admin"}
    ])

    conn.close()


@retry(stop=stop_after_attempt(5),
    wait=wait_fixed(2),
    before_sleep=before_sleep_log(_LOGGER, logging.DEBUG))
def main():
    test_config_path = CURRENT_DIR.parent / "config" / "server-host-test.yaml"
    config = read_and_validate(test_config_path.as_posix())
    pg_config = config["postgres"]

    test_engine = acquire_engine(DNS.format(**pg_config))

    _LOGGER.info("Setting up db ...")
    setup_db(pg_config)
    _LOGGER.info("")

    _LOGGER.info("Creating tables ...")
    create_tables(engine=test_engine)

    _LOGGER.info("Adding sample data ...")
    sample_data(engine=test_engine)

    _LOGGER.info("Droping ...")
    drop_tables(test_engine)
    teardown_db(pg_config)


if __name__ == "__main__":
    main()
    _LOGGER.info("Main retry stats: %s", main.retry.statistics)
