import pytest
import redislite
from pymongo_inmemory import MongoClient

from scheduler import config
from scheduler.dbs.redis import get_redis_pool

_MONGO_CLIENT = None


@pytest.fixture(scope="session", autouse=True)
def inmemory_mongodb():
    # this is an actual instance in memory running on a separate thread
    # testing everything against real MongoDB.
    # Only downside is it takes a almost 6 seconds to start the first time

    global _MONGO_CLIENT  # pylint: disable=global-statement
    _MONGO_CLIENT = MongoClient(host="0.0.0.0", port=27017)
    yield
    _MONGO_CLIENT.close()


@pytest.fixture(autouse=True)
def inmemory_mongodb_clenup_before_each_test():
    # dropping the entire database between each test run

    global _MONGO_CLIENT  # pylint: disable=global-statement
    _MONGO_CLIENT.drop_database(config.mongo_db_name)


@pytest.fixture(scope="session", autouse=True)
def inmemory_redis():
    config.redis_host = "localhost"
    server = redislite.Redis(serverconfig={"port": config.redis_port})
    # ensure teardown when it goes out of scope
    yield
    server.close()


@pytest.fixture(autouse=True)
@pytest.mark.asyncio
async def redis_flush_before_each_test():
    # dropping the entire database between each test run
    async with get_redis_pool() as redis_pool:
        await redis_pool.flushall()
