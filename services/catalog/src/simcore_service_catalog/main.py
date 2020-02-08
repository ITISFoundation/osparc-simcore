import logging

from fastapi import FastAPI

from . import __version__
from .config import is_testing_enabled
from .db import create_tables, setup_engine, teardown_engine
from .endpoints import diagnostics, dusers

API_VERSION = __version__
API_MAJOR_VERSION = API_VERSION.split(".")[0]

log = logging.getLogger(__name__)

app = FastAPI(
    title="Components Catalog Service",
    # TODO: get here extended description from setup
    description="Manages and maintains a **catalog** of all published components (e.g. macro-algorithms, scripts, etc)",
    version=API_VERSION,
    openapi_url=f"/v{API_MAJOR_VERSION}/openapi.json"
)

# projects
app.include_router(diagnostics.router, tags=['diagnostics'])
app.include_router(dusers.router, tags=['dummy'], prefix=f"/v{API_MAJOR_VERSION}")


@app.on_event("startup")
def startup_event():
    # TODO: logging
    log.info( "Application started")
    if is_testing_enabled:
        # TODO: retry?
        log.info( "Creating tables")
        create_tables()


@app.on_event("startup")
async def start_db():
    # TODO: retry here, access to another server
    await setup_engine()


@app.on_event("shutdown")
def shutdown_event():
    log.info("Application shutdown")

@app.on_event("shutdown")
async def shutdown_db():
    await teardown_engine()





## DEBUG: uvicorn simcore_service_components_catalog.main:app --reload
# TODO: use entry-point to call uvicorn's entrypoint above
