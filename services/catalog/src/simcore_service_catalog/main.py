from datetime import datetime

from fastapi import FastAPI

from .__version__ import __version__
from .config import is_testing_enabled
from .db import create_tables, setup_engine, teardown_engine
from .endpoints import project_router

API_VERSION = __version__
API_MAJOR_VERSION = API_VERSION.split(".")[0]


app = FastAPI(
    title="My Super Project",
    description="This is a very fancy project, with auto docs for the API and everything",
    version=API_VERSION,
    openapi_url=f"/api/v{API_MAJOR_VERSION}/openapi.json"
)

# projects
app.include_router(project_router, prefix=f"/api/v{API_MAJOR_VERSION}")
#app.include_router(project_router, prefix="/api/latest")


@app.on_event("startup")
def startup_event():
    # TODO: logging
    with open("log.txt", mode="a") as log:
        print( f"{datetime.now()}:" ,"Application startup", file=log)
        if is_testing_enabled:
            # retry?
            create_tables()
            print( f"{datetime.now()}:" ,"Created Tables", file=log)


@app.on_event("startup")
async def start_db():
    # TODO: retry here, access to another server
    await setup_engine()


@app.on_event("shutdown")
def shutdown_event():
    with open("log.txt", mode="a") as log:
        print( f"{datetime.now()}:" ,"Application shutdown", file=log)


@app.on_event("shutdown")
async def shutdown_db():
    await teardown_engine()





## DEBUG: uvicorn simcore_service_components_catalog.main:app --reload
# TODO: use entry-point to call uvicorn's entrypoint above
