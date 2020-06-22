import json
import logging
import types
from pathlib import Path
from typing import Dict

import yaml
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute

from .redoc import add_vendor_extensions, compose_long_description

logger = logging.getLogger(__name__)


def override_openapi_method(app: FastAPI):
    # TODO: test openapi(*) member does not change interface

    def _custom_openapi_method(zelf: FastAPI, openapi_prefix: str = "") -> Dict:
        """ Overrides FastAPI.openapi member function
            returns OAS schema with vendor extensions
        """
        if not zelf.openapi_schema:

            desc = compose_long_description(zelf.description)
            openapi_schema = get_openapi(
                title=zelf.title,
                version=zelf.version,
                openapi_version=zelf.openapi_version,
                description=desc,
                routes=zelf.routes,
                openapi_prefix=openapi_prefix,
                tags=zelf.openapi_tags,
            )

            add_vendor_extensions(openapi_schema)

            zelf.openapi_schema = openapi_schema
        return zelf.openapi_schema

    app.openapi = types.MethodType(_custom_openapi_method, app)


def use_route_names_as_operation_ids(app: FastAPI) -> None:
    """
    Overrides default operation_ids assigning the same name as the handler functions

    MUST be called only after all routes have been added.

    PROS: auto-generated client has one-to-one correspondence and human readable names
    CONS: highly coupled. Changes in server handler names will change client
    """
    for route in app.routes:
        if isinstance(route, APIRoute):
            route.operation_id = route.name


def dump_openapi(app: FastAPI, filepath: Path):
    logger.info("Dumping openapi specs as %s", filepath)
    with open(filepath, "wt") as fh:
        if filepath.suffix == ".json":
            json.dump(app.openapi(), fh, indent=2)
        elif filepath.suffix in (".yaml", ".yml"):
            yaml.safe_dump(app.openapi(), fh)
        else:
            raise ValueError("invalid")
