import logging
import sys
from pathlib import Path

import yaml
from fastapi import FastAPI
from tenacity import Retrying, before_sleep_log, stop_after_attempt, wait_fixed

from .__version__ import api_version, api_version_prefix
from .config import is_testing_enabled
from .db import create_tables, setup_engine, teardown_engine
from .endpoints import dags, diagnostics
from .remote_debug import setup_remote_debugging

current_dir = Path(sys.argv[0] if __name__ ==
                   "__main__" else __file__).resolve().parent

log = logging.getLogger(__name__)


app = FastAPI(
    debug=is_testing_enabled,
    title="Components Catalog Service",
    # TODO: get here extended description from setup
    description="Manages and maintains a **catalog** of all published components (e.g. macro-algorithms, scripts, etc)",
    version=api_version,
    openapi_url=f"/{api_version_prefix}/openapi.json"
)

# projects
app.include_router(diagnostics.router, tags=['diagnostics'])
app.include_router(dags.router, tags=['dags'], prefix=f"/{api_version_prefix}")


def dump_openapi():
    oas_path: Path = current_dir / f"api/{api_version_prefix}/openapi.yaml"
    log.info("Saving openapi schema to %s", oas_path)
    with open(oas_path, 'wt') as fh:
        yaml.safe_dump(app.openapi(), fh)


@app.on_event("startup")
def startup_event():
    log.info("Application started")
    setup_remote_debugging()


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
