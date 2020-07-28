import asyncio

from async_timeout import timeout
from motor.motor_asyncio import AsyncIOMotorClient
from tenacity import retry, stop_after_delay, wait_random_exponential
from umongo import MotorAsyncIOInstance

from scheduler import config

# MongoDB instance to be used by all models
instance = MotorAsyncIOInstance()  # pylint: disable=invalid-name


async def ensure_indexes():
    from scheduler.dbs.mongo_models.workbench import WorkbenchDiff, WorkbenchUpdate

    # this can also be done by providing the module and plying auto discovery
    await WorkbenchUpdate.ensure_indexes()
    await WorkbenchDiff.ensure_indexes()


# @retry(wait=wait_random_exponential(multiplier=1, max=3), stop=stop_after_delay(10))
async def initialize_mongo_driver():
    """Will initialize the driver and try to access the database """
    # pylint: disable=global-statement
    global instance  # pylint: disable=invalid-name

    client = AsyncIOMotorClient(config.mongo_uri, io_loop=asyncio.get_event_loop())
    database = client[config.mongo_db_name]
    instance.init(database)

    # check if it can connect
    async with timeout(5):
        await database.responsiveness_collection.insert_one({"k": "v"})
        await database.responsiveness_collection.drop()

    # ensure collection indexes
    await ensure_indexes()
