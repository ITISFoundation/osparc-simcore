""" Helper script to generate OAS automatically NIH-sparc portal API section
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from enum import Enum
from typing import Optional, Union

from fastapi import FastAPI, status
from fastapi.responses import RedirectResponse
from models_library.generics import Envelope
from models_library.projects import ProjectID
from pydantic import HttpUrl, PositiveInt, constr
from simcore_service_webserver.studies_dispatcher.handlers_redirects import (
    KEY_RE,
    VERSION_RE,
)
from simcore_service_webserver.studies_dispatcher.handlers_rest import Viewer

app = FastAPI(redoc_url=None)

TAGS: list[Union[str, Enum]] = [
    "sparc",
]


@app.post(
    "/viewers",
    response_model=Envelope[list[Viewer]],
    tags=TAGS,
    operation_id="list_viewers",
)
async def list_viewers(file_type: Optional[str] = None):
    """Lists all publically available viewers

    Notice that this might contain multiple services for the same filetype

    If file_type is provided, then it filters viewer for that filetype
    """


@app.post(
    "/viewers/default",
    response_model=Envelope[list[Viewer]],
    tags=TAGS,
    operation_id="list_default_viewers",
)
async def list_default_viewers(file_type: Optional[str] = None):
    """Lists the default viewer for each supported filetype

    This was interfaced as a subcollection of viewers because it is a very common use-case

    Only publicaly available viewers

    If file_type is provided, then it filters viewer for that filetype
    """


@app.get(
    "/view",
    response_class=RedirectResponse,
    response_description="Opens osparc and starts viewer for selected data",
    status_code=status.HTTP_302_FOUND,
    tags=TAGS,
    operation_id="get_redirection_to_viewer",
)
async def get_redirection_to_viewer(
    file_type: str,
    viewer_key: constr(regex=KEY_RE),
    viewer_version: constr(regex=VERSION_RE),
    file_size: PositiveInt,
    download_link: HttpUrl,
    file_name: Optional[str] = "unknown",
):
    """Opens a viewer in osparc for data in the NIH-sparc portal"""


@app.get(
    "/study/{study_id}",
    tags=TAGS,
    response_class=RedirectResponse,
    response_description="Opens osparc and opens a copy of publised study",
    status_code=status.HTTP_302_FOUND,
    operation_id="get_redirection_to_study_page",
)
async def get_redirection_to_study_page(study_id: ProjectID):
    """Opens a study published in osparc"""


if __name__ == "__main__":

    from _common import CURRENT_DIR, create_openapi_specs

    create_openapi_specs(app, CURRENT_DIR.parent / "openapi-nih-sparc.yaml")
