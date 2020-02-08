import logging

from fastapi import FastAPI
from tenacity import Retrying, before_sleep_log, stop_after_attempt, wait_fixed

from . import __version__
from .config import is_testing_enabled
from .db import create_tables, setup_engine, teardown_engine
from .endpoints import dags, diagnostics, dusers

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
app.include_router(dags.router, tags=['dags'], prefix=f"/v{API_MAJOR_VERSION}")
app.include_router(dusers.router, tags=['dummy'], prefix=f"/v{API_MAJOR_VERSION}")


@app.on_event("startup")
def startup_event():
    log.info( "Application started")


@app.on_event("startup")
async def start_db():
    log.info("Initializing db")

    retry_policy = dict(
        wait=wait_fixed(5),
        stop=stop_after_attempt(20),
        before_sleep=before_sleep_log(log, logging.WARNING),
        reraise=True
    )
    for attempt in Retrying(**retry_policy):
        with attempt:
            await setup_engine()

    if is_testing_enabled:
        log.info("Creating db tables (testing mode)")
        create_tables()


@app.on_event("shutdown")
def shutdown_event():
    log.info("Application shutdown")

@app.on_event("shutdown")
async def shutdown_db():
    log.info("Shutting down db")
    await teardown_engine()

## DEBUG: uvicorn simcore_service_components_catalog.main:app --reload
# TODO: use entry-point to call uvicorn's entrypoint above
