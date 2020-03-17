""" Helpers wrapping or producing FastAPI's app

"""
import json
from pathlib import Path
from typing import Callable

import yaml
from fastapi import FastAPI

from .__version__ import api_version, api_version_prefix
from .config import is_testing_enabled


def create() -> FastAPI:
    # factory
    app = FastAPI(
        debug=is_testing_enabled,
        title="Public API Gateway",
        description="Platform's API Gateway for external clients",
        version=api_version,
        openapi_url=f"/api/{api_version_prefix}/openapi.json",
    )

    return app


def add_startup_handler(app: FastAPI, startup_event: Callable):
    app.router.add_event_handler("startup", startup_event)


def add_shutdown_handler(app: FastAPI, shutdown_event: Callable):
    app.router.add_event_handler("shutdown", shutdown_event)


def dump_openapi(app: FastAPI, filepath: Path):
    # TODO: fix sections order so it is human readable
    # TODO: if filepath is None create dumps to stream
    with open(filepath, "wt") as fh:
        if filepath.suffix == ".json":
            json.dump(app.openapi(), fh, indent=2)
        elif filepath.suffix in (".yaml", ".yml"):
            yaml.safe_dump(app.openapi(), fh)
        else:
            raise ValueError("invalid")
