import json
import types
from pathlib import Path
from typing import Dict

import yaml
from fastapi import FastAPI
from fastapi.openapi.docs import get_redoc_html
from fastapi.openapi.utils import get_openapi

from .__version__ import api_version, api_vtag
from .settings import AppSettings

FAVICON = "https://osparc.io/resource/osparc/favicon.png"
LOGO = "https://raw.githubusercontent.com/ITISFoundation/osparc-manual/b809d93619512eb60c827b7e769c6145758378d0/_media/osparc-logo.svg"
PYTHON_CODE_SAMPLES_BASE_URL = "https://raw.githubusercontent.com/ITISFoundation/osparc-simcore-python-client/master/code_samples"


def _custom_openapi(zelf: FastAPI) -> Dict:
    """ Overrides FastAPI.openapi member function
        returns OAS schema with vendor extensions
    """
    if not zelf.openapi_schema:
        desc = f"**{zelf.description}**\n"
        desc += "## Python Client\n"
        desc += "- Github [repo](https://github.com/ITISFoundation/osparc-simcore-python-client)\n"
        desc += "- Quick install: ``pip install git+https://github.com/ITISFoundation/osparc-simcore-python-client.git``\n"

        openapi_schema = get_openapi(
            title=zelf.title,
            version=zelf.version,
            openapi_version=zelf.openapi_version,
            description=desc,
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
        # TODO: check that all url are available before exposing
        openapi_schema["paths"][f"/{api_vtag}/meta"]["get"]["x-code-samples"] = [
            {
                "lang": "python",
                "source": {"$ref": f"{PYTHON_CODE_SAMPLES_BASE_URL}/meta/get.py"},
            },
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
    """  Creates a customized app

    """
    app = FastAPI(
        debug=settings.debug,
        title="Public API Gateway",
        description="osparc-simcore Public RESTful API Specifications",
        version=api_version,
        openapi_url=f"/api/{api_vtag}/openapi.json",
        redoc_url=None,
    )
    app.state.settings = settings

    # overrides generation of openapi specs
    app.openapi = types.MethodType(_custom_openapi, app)

    # customizes rendering of redoc
    _setup_redoc(app)

    return app


def get_settings(app: FastAPI) -> AppSettings:
    """ Read-only app settings """
    return app.state.settings


def dump_openapi(app: FastAPI, filepath: Path):
    with open(filepath, "wt") as fh:
        if filepath.suffix == ".json":
            json.dump(app.openapi(), fh, indent=2)
        elif filepath.suffix in (".yaml", ".yml"):
            yaml.safe_dump(app.openapi(), fh)
        else:
            raise ValueError("invalid")
