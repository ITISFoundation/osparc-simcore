""" Handles request to the viewers redirection entrypoints

"""
import logging
import urllib.parse
from typing import Optional

import aiohttp
from aiohttp import web
from aiohttp.client_exceptions import ClientError
from models_library.services import KEY_RE, VERSION_RE
from pydantic import BaseModel, HttpUrl, ValidationError, constr, validator
from pydantic.types import PositiveInt

from ..products import get_product_name
from ..utils_aiohttp import create_redirect_response
from ._core import StudyDispatcherError, ViewerInfo, validate_requested_viewer
from ._projects import acquire_project_with_viewer
from ._users import UserInfo, acquire_user, ensure_authentication

log = logging.getLogger(__name__)


# HANDLERS --------------------------------
class ViewerQueryParams(BaseModel):
    file_type: str
    viewer_key: constr(regex=KEY_RE)  # type: ignore
    viewer_version: constr(regex=VERSION_RE)  # type: ignore

    @staticmethod
    def from_viewer(viewer: ViewerInfo) -> "ViewerQueryParams":
        # can safely construct w/o validation from a viewer
        return ViewerQueryParams.construct(
            file_type=viewer.filetype,
            viewer_key=viewer.key,
            viewer_version=viewer.version,
        )


SPACE = " "


class RedirectionQueryParams(ViewerQueryParams):
    file_name: Optional[str] = "unknown"
    file_size: PositiveInt
    download_link: HttpUrl

    @validator("download_link", pre=True)
    @classmethod
    def unquote_url(cls, v):
        # NOTE: see test_url_quoting_and_validation
        # before any change here
        w = urllib.parse.unquote(v)
        if SPACE in w:
            w = w.replace(SPACE, "%20")
        return w

    @classmethod
    def from_request(cls, request: web.Request) -> "RedirectionQueryParams":
        try:
            obj = cls.parse_obj(dict(request.query))
        except ValidationError as err:
            raise web.HTTPBadRequest(
                content_type="application/json",
                body=err.json(),
                reason=f"{len(err.errors())} invalid parameters in query",
            )
        else:
            return obj

    async def check_download_link(self):
        """Explicit validation of download link that performs a light fetch of url's head"""
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


def compose_dispatcher_prefix_url(request: web.Request, viewer: ViewerInfo) -> str:
    """This is denoted PREFIX URL because it needs to append extra query
    parameters added in RedirectionQueryParams
    """
    params = ViewerQueryParams.from_viewer(viewer).dict()
    absolute_url = request.url.join(
        request.app.router["get_redirection_to_viewer"].url_for().with_query(**params)
    )
    return str(absolute_url)


async def get_redirection_to_viewer(request: web.Request):
    try:
        # query parameters in request parsed and validated
        params: RedirectionQueryParams = RedirectionQueryParams.from_request(request)
        log.debug("Requesting viewer %s", params)

        # TODO: Cannot check file_size from HEAD
        # removed await params.check_download_link()
        # Perhaps can check the header for GET while downloading and retreive file_size??

        # pylint: disable=no-member
        viewer: ViewerInfo = await validate_requested_viewer(
            request.app,
            file_type=params.file_type,
            file_size=params.file_size,
            service_key=params.viewer_key,
            service_version=params.viewer_version,
        )
        log.debug("Validated viewer %s", viewer)

        # Retrieve user or create a temporary guest
        user: UserInfo = await acquire_user(
            request, is_guest_allowed=viewer.is_guest_allowed
        )
        log.debug("User acquired %s", user)

        # Generate one project per user + download_link + viewer
        project_id, viewer_id = await acquire_project_with_viewer(
            request.app,
            user,
            viewer,
            params.download_link,
            product_name=get_product_name(request),
        )
        log.debug("Project acquired '%s'", project_id)

        # Redirection and creation of cookies (for guests)
        # Produces  /#/view?project_id= & viewer_node_id
        response = create_redirect_response(
            request.app,
            page="view",
            project_id=project_id,
            viewer_node_id=viewer_id,
            file_name=params.file_name or "unkwnown",
            file_size=params.file_size,
        )
        await ensure_authentication(user, request, response)
        log.debug(
            "Response with redirect '%s' w/ auth cookie in headers %s)",
            response,
            response.headers,
        )

    except StudyDispatcherError as err:
        raise create_redirect_response(
            request.app,
            page="error",
            message=f"Sorry, we cannot render this file: {err.reason}",
            status_code=web.HTTPUnprocessableEntity.status_code,  # 422
        ) from err

    except (web.HTTPUnauthorized) as err:
        raise create_redirect_response(
            request.app,
            page="error",
            message=f"{err.reason}. Please reload this page to login/register.",
            status_code=err.status_code,
        ) from err

    except (web.HTTPClientError) as err:
        log.exception("Client error with status code %d", err.status_code)
        raise create_redirect_response(
            request.app, page="error", message=err.reason, status_code=err.status_code
        ) from err

    except (ValidationError, web.HTTPServerError, Exception) as err:
        log.exception("Fatal error while redirecting %s", request.query)
        raise create_redirect_response(
            request.app,
            page="error",
            message="Something went wrong while processing your request.",
            status_code=web.HTTPInternalServerError.status_code,
        ) from err

    return response
