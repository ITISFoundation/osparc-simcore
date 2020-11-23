""" Handles request to the viewers redirection entrypoints

"""
import logging
import urllib.parse
from typing import Optional

import aiohttp
from aiohttp import web
from aiohttp.client_exceptions import ClientError
from pydantic import BaseModel, HttpUrl, ValidationError, validator
from pydantic.types import PositiveInt
from yarl import URL

from ..statics import INDEX_RESOURCE_NAME
from ._core import (
    MatchNotFoundError,
    ValidationMixin,
    ViewerInfo,
    find_compatible_viewer,
)
from ._projects import acquire_project_with_viewer
from ._users import UserInfo, acquire_user, ensure_authentication

log = logging.getLogger(__name__)


def create_redirect_response(
    app: web.Application, page: str, **parameters
) -> web.HTTPFound:
    """
    Returns a redirect response to the front-end with information on page and parameters embedded in the fragment.

    For instance,
        https://osparc.io/#/error?message=Sorry%2C%20I%20could%20not%20find%20this%20&status_code=404
    results from
            - page=error
        and parameters
            - message="Sorry, I could not find this"
            - status_code=404
    """
    page = page.strip(" /")
    # TODO: test that fragment queries are understood by front-end
    # TODO: front end should create an error page and a view page
    assert page in ("view", "error")  # nosec
    in_fragment = str(URL.build(path=f"/{page}").with_query(**parameters))
    redirect_url = app.router[INDEX_RESOURCE_NAME].url_for().with_fragment(in_fragment)
    return web.HTTPFound(location=redirect_url)


# HANDLERS --------------------------------


class QueryParams(BaseModel, ValidationMixin):
    # TODO: create dinamically with pydantic class
    file_name: Optional[str] = None
    file_size: PositiveInt
    file_type: str  # TODO: should we define some types?
    download_link: HttpUrl

    @validator("download_link", pre=True)
    @classmethod
    def decode_downloadlink(cls, v):
        return urllib.parse.unquote(v)

    async def check_download_link(self):
        """Explicit validation of download link that performs a light fetch of url's hea"""
        #
        # WARNING: Do not use this check with Amazon download links
        #          since HEAD operation is forbidden!
        try:
            async with aiohttp.request("HEAD", self.download_link) as response:
                response.raise_for_status()

        except ClientError as err:
            log.debug(
                "Invalid download link '%s'. If failed fetch check with %s",
                self.download_link,
                err,
            )
            raise web.HTTPBadRequest(
                reason="The download link provided is invalid"
            ) from err


async def get_redirection_to_viewer(request: web.Request):
    try:
        # query parameters in request parsed and validated
        params = QueryParams.from_request(request)
        # TODO: removed await params.check_download_link()

        viewer: ViewerInfo = find_compatible_viewer(
            file_type=params.file_type, file_size=params.file_size
        )

        # Retrieve user or create a temporary guest
        user: UserInfo = await acquire_user(request)

        # Generate one project per user + download_link + viewer
        project_id, viewer_id = await acquire_project_with_viewer(
            request.app, user, viewer, params.download_link
        )

        # Redirection and creation of cookies (for guests)
        # Produces  /#/view?project_id= & viewer_node_id
        response = create_redirect_response(
            request.app,
            page="view",
            project_id=project_id,
            viewer_node_id=viewer_id,
            file_name=params.file_name,
            file_size=params.file_size,
        )
        await ensure_authentication(user, request, response)

    except MatchNotFoundError as err:
        raise create_redirect_response(
            request.app,
            page="error",
            message=f"Sorry, we cannot render this file: {err.reason}",
            status_code= web.HTTPUnprocessableEntity.status_code # 422
        )
    except web.HTTPClientError as err:
        raise create_redirect_response(
            request.app, page="error", message=err.reason, status_code=err.status_code
        )
    except (ValidationError, web.HTTPServerError, Exception):
        log.exception("Fatal error while redirecting %s", request.query)
        raise create_redirect_response(
            request.app,
            page="error",
            message="Ups something went wrong while processing your request.",
            status_code=web.HTTPServerError.status_code
        )
    return response
