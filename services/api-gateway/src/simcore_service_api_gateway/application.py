""" Helpers wrapping or producing FastAPI's app

    These helpers are typically used with main.the_app singleton instance
"""
import json
import types
from pathlib import Path
from typing import Callable, Dict

import yaml
from fastapi import FastAPI
from fastapi.openapi.docs import get_redoc_html
from fastapi.openapi.utils import get_openapi

from .__version__ import api_version, api_vtag
from .settings import AppSettings

FAVICON = "https://osparc.io/resource/osparc/favicon.png"
LOGO = "https://raw.githubusercontent.com/ITISFoundation/osparc-manual/b809d93619512eb60c827b7e769c6145758378d0/_media/osparc-logo.svg"


def _custom_openapi(zelf: FastAPI) -> Dict:
    if not zelf.openapi_schema:
        openapi_schema = get_openapi(
            title=zelf.title,
            version=zelf.version,
            openapi_version=zelf.openapi_version,
            description=zelf.description,
            routes=zelf.routes,
            openapi_prefix=zelf.openapi_prefix,
        )

        # ReDoc vendor extensions
        # SEE https://github.com/Redocly/redoc/blob/master/docs/redoc-vendor-extensions.md
        openapi_schema["info"]["x-logo"] = {
            "url": LOGO,
            "altText": "osparc-simcore logo",
        }

        #
        # TODO: load code samples add if function is contained in sample
        # TODO: See if openapi-cli does this already
        #
        openapi_schema["paths"]["/meta"]["get"]["x-code-samples"] = [
            {"lang": "python", "source": "print('hello world')",},
        ]

        zelf.openapi_schema = openapi_schema
    return zelf.openapi_schema


def _setup_redoc(app: FastAPI):
    from fastapi.applications import Request, HTMLResponse

    async def redoc_html(_req: Request) -> HTMLResponse:
        return get_redoc_html(
            openapi_url=app.openapi_url,
            title=app.title + " - redoc",
            redoc_favicon_url=FAVICON,
        )

    app.add_route("/redoc", redoc_html, include_in_schema=False)


def create(settings: AppSettings) -> FastAPI:
    # factory
    app = FastAPI(
        debug=settings.debug,
        title="Public API Gateway",
        description="osparc-simcore Public RESTful API Specifications",
        version=api_version,
        openapi_url=f"/api/{api_vtag}/openapi.json",
        redoc_url=None,
    )
    app.state.settings = settings

    app.openapi = types.MethodType(_custom_openapi, app)

    _setup_redoc(app)

    return app


def get_settings(app: FastAPI) -> AppSettings:
    """ Read-only app settings """
    return app.state["settings"].copy()


def add_startup_handler(app: FastAPI, startup_event: Callable):
    # TODO: this is different from fastapi_shortcuts
    # Add Callable with and w/o arguments?
    app.router.add_event_handler("startup", startup_event)


def add_shutdown_handler(app: FastAPI, shutdown_event: Callable):
    app.router.add_event_handler("shutdown", shutdown_event)


def dump_openapi(app: FastAPI, filepath: Path):
    with open(filepath, "wt") as fh:
        if filepath.suffix == ".json":
            json.dump(app.openapi(), fh, indent=2)
        elif filepath.suffix in (".yaml", ".yml"):
            yaml.safe_dump(app.openapi(), fh)
        else:
            raise ValueError("invalid")
