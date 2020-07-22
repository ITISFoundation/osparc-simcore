# pylint: disable=wrong-import-position
from fastapi import FastAPI

app = FastAPI()

# imports all submodules to ensure service discovery
from scheduler import api as _  # pylint: disable=unused-import
from scheduler.dbs.mongo_models import initialize_mongo_driver


@app.on_event("startup")
async def startup_event():
    await initialize_mongo_driver()


@app.on_event("shutdown")
async def shutdown_event():
    pass
