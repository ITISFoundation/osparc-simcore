from typing import Callable, Dict

from fastapi import FastAPI
from fastapi.applications import HTMLResponse, Request
from fastapi.openapi.docs import get_redoc_html

# from ..__version__ import api_vtag

FAVICON = "https://osparc.io/resource/osparc/favicon.png"
LOGO = "https://raw.githubusercontent.com/ITISFoundation/osparc-manual/b809d93619512eb60c827b7e769c6145758378d0/_media/osparc-logo.svg"
PYTHON_CODE_SAMPLES_BASE_URL = "https://raw.githubusercontent.com/ITISFoundation/osparc-simcore-python-client/master/code_samples"


def compose_long_description(description: str) -> str:
    desc = f"**{description}**\n"
    desc += "## Python Library\n"
    desc += "- Documentation (https://itisfoundation.github.io/osparc-simcore-python-client/#/)\n"
    desc += "- Quick install: ``pip install git+https://github.com/ITISFoundation/osparc-simcore-python-client.git``\n"

    return desc


def add_vendor_extensions(openapi_schema: Dict):
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
    # openapi_schema["paths"][f"/{api_vtag}/meta"]["get"]["x-code-samples"] = [
    #     {
    #         "lang": "python",
    #         "source": {"$ref": f"{PYTHON_CODE_SAMPLES_BASE_URL}/meta/get.py"},
    #     },
    # ]


def create_redoc_handler(app: FastAPI) -> Callable:
    async def _redoc_html(_req: Request) -> HTMLResponse:
        return get_redoc_html(
            openapi_url=app.openapi_url,
            title=app.title + " - redoc",
            redoc_favicon_url=FAVICON,
        )

    return _redoc_html
