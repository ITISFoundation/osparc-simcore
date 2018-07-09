import pytest
import sqlalchemy as sa
 
from server.config import get_config, SRC_DIR
from server.db import (create_aiopg, dispose_aiopg)
from server.model import (users, permissions)


async def test_basic_db_workflow(postgres_service):
  """
  create engine
  connect
  query 
  check against expected
  disconnect
  """
  TEST_CONFIG_PATH = SRC_DIR / 'config' / 'server-test.yaml'

  app = {'config': get_config(['-c', TEST_CONFIG_PATH.as_posix()])}
  await create_aiopg(app)

  # creates new engine!
  assert 'db_engine' in app
  engine = app['db_engine']

  async with engine.acquire() as conn:
    where = sa.and_(users.c.is_superuser, sa.not_(users.c.disabled))
    #where = users.c.is_superuser
    query = users.count().where(where)
    ret = await conn.scalar(query)
    assert ret == 1

  await dispose_aiopg(app)
  assert engine.closed

