import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from tenacity import Retrying

from . import app_factory
from .config import is_testing_enabled
from .db import create_tables, pg_retry_policy, setup_engine, teardown_engine
from .utils.remote_debug import setup_remote_debugging

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

log = logging.getLogger(__name__)

app: FastAPI = app_factory.create()


# EVENTS ----
# TODO: move to app_factory.py
@app.on_event("startup")
def startup_event():
    log.info("Application started")
    setup_remote_debugging()


@app.on_event("startup")
async def start_db():
    log.info("Initializing db")

    for attempt in Retrying(**pg_retry_policy(log)):
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


# #
# current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

# with open(current_dir / "openapi.json", "wt") as fh:
#     json.dump(app.openapi(), fh, indent=2)
# NOTE: yaml.safe_dumps(app.openapi())
