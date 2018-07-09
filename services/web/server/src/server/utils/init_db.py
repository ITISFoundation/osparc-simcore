""" Initializes tables in database and adds some sample data for testing

FIXME: this place does not fill right... see how this script is called
FIXME: check https://github.com/aio-libs/aiohttp_admin/blob/master/demos/blog/aiohttpdemo_blog/generate_data.py
FIXME: rename as server.dev.generate_data.py and set dev as an optional sub-package as server[dev]

References:
[1]:https://github.com/aio-libs/aiohttp-demos/blob/master/docs/preparations.rst#environment
"""
import logging
import os

from passlib.hash import sha256_crypt
from sqlalchemy import (MetaData,
                        create_engine)
from tenacity import (retry,
                      stop_after_attempt,
                      wait_fixed)

from server.config import (SRC_DIR,
                           get_config)
from server.model import (permissions,
                          users)

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)


DSN = "postgresql://{user}:{password}@{host}:{port}/{database}"


USER_CONFIG_PATH = SRC_DIR / 'config' / 'server.yaml'
USER_CONFIG = get_config(['-c', USER_CONFIG_PATH.as_posix()])
USER_DB_URL = DSN.format(**USER_CONFIG['postgres'])
user_engine = create_engine(USER_DB_URL)

TEST_CONFIG_PATH = SRC_DIR / 'config' / 'server-test.yaml'
TEST_CONFIG = get_config(['-c', TEST_CONFIG_PATH.as_posix()])
TEST_DB_URL = DSN.format(**TEST_CONFIG['postgres'])
test_engine = create_engine(TEST_DB_URL)

# FIXME: admin user/passwords and in sync with other host/port configs
ADMIN_DB_URL = DSN.format(
    user='postgres',
    password='postgres',
    database='postgres',
    host=USER_CONFIG['postgres']['host'],
    port=5432
)

# TODO: what is isolation_level?
admin_engine = create_engine(ADMIN_DB_URL, isolation_level='AUTOCOMMIT')


def setup_db(config):
    db_name = config['database']
    db_user = config['user']
    db_pass = config['password']

    # TODO: compose using query semantics. Clarify pros/cons vs string cli?
    conn = admin_engine.connect()
    conn.execute("DROP DATABASE IF EXISTS %s" % db_name)
    conn.execute("DROP ROLE IF EXISTS %s" % db_user)
    conn.execute("CREATE USER %s WITH PASSWORD '%s'" % (db_user, db_pass))
    conn.execute("CREATE DATABASE %s ENCODING 'UTF8'" % db_name)
    conn.execute("GRANT ALL PRIVILEGES ON DATABASE %s TO %s" %
                 (db_name, db_user))
    conn.close()


def teardown_db(config):

    db_name = config['database']
    db_user = config['user']

    conn = admin_engine.connect()
    conn.execute("""
      SELECT pg_terminate_backend(pg_stat_activity.pid)
      FROM pg_stat_activity
      WHERE pg_stat_activity.datname = '%s'
        AND pid <> pg_backend_pid();""" % db_name)
    conn.execute("DROP DATABASE IF EXISTS %s" % db_name)
    conn.execute("DROP ROLE IF EXISTS %s" % db_user)
    conn.close()


def create_tables(engine=test_engine):
    meta = MetaData()
    meta.create_all(bind=engine, tables=[users, permissions])


def drop_tables(engine=test_engine):
    meta = MetaData()
    meta.drop_all(bind=engine, tables=[users, permissions])


def sample_data(engine=test_engine):

    generate_password_hash = sha256_crypt.hash

    #TODO: use fake
    conn = engine.connect()
    conn.execute(users.insert(), [
        {'login': 'bizzy@itis.ethz.ch',
         'passwd': generate_password_hash('z43'),
         'is_superuser': False,
         'disabled': False},
        {'login': 'pcrespov@foo.com',
         'passwd': generate_password_hash('123'),
         'is_superuser': True,
         'disabled': False},
        {'login': 'mrspam@bar.io',
         'passwd': generate_password_hash('345'),
         'is_superuser': True,
         'disabled': True}
    ])

    conn.execute(permissions.insert(), [
        {'user_id': 1,
         'perm_name': 'tester'},
        {'user_id': 2,
         'perm_name': 'admin'}
    ])

    conn.close()


@retry(stop=stop_after_attempt(5), wait=wait_fixed(2))
def main():

    config = USER_CONFIG['postgres']
    engine = user_engine

    _LOGGER.info("Setting up db ...")
    setup_db(config)
    _LOGGER.info("")

    _LOGGER.info("Creating tables ...")
    create_tables(engine=engine)

    _LOGGER.info("Adding sample data ...")
    sample_data(engine=engine)

    # drop_tables()
    # teardown_db(config)


if __name__ == '__main__':
    main()
