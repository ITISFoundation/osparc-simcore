""" Handles request to the viewers redirection entrypoints

"""
import logging
from typing import Optional

from aiohttp import web
from pydantic import BaseModel, HttpUrl, ValidationError
from yarl import URL

from ..statics import INDEX_RESOURCE_NAME
from ._core import (
    MatchNotFoundError,
    ValidationMixin,
    ViewerInfo,
    compose_uuid_from,
    find_compatible_viewer,
)
from ._projects import create_viewer_project_model
from ._users import UserInfo, acquire_user, ensure_authentication

log = logging.getLogger(__name__)


def create_redirect_response(app: web.Application, page: str, **parameters):
    page = page.strip(" /")
    # TODO: test that fragment queries are understood by front-end
    # TODO: front end should create an error page and a view page
    assert page in ("view", "error")  # nosec

    in_fragment = str(URL.build(path=f"/{page}").with_query(**parameters))
    redirect_url = app.router[INDEX_RESOURCE_NAME].url_for().with_fragment(in_fragment)
    return web.HTTPFound(location=redirect_url)


# HANDLERS --------------------------------
class RequestParams(BaseModel, ValidationMixin):
    # TODO: create dinamically with pydantic class
    file_name: Optional[str] = None
    file_size: int
    file_type: str
    download_link: HttpUrl


async def get_redirection_to_viewer(request: web.Request):
    try:
        p = RequestParams.create_from(request)  # validated parameters

        viewer: ViewerInfo = find_compatible_viewer(p.file_size, p.file_type)

        # retrieve user or create a temporary guest
        user: UserInfo = await acquire_user(request)

        # Generate one project per user + download_link + viewer
        project_id = compose_uuid_from(user.email, viewer.footprint, p.download_link)

        # TODO:
        #
        # already exists?
        #   yes. user has access??
        #       yes:
        #          redirect
        #       no:
        #          give user access to project
        #          save projct
        #          redirect
        #   no:
        #       create new
        #       save
        #       redirect

        # create project with file-picker (download_link) and viewer
        project = create_viewer_project_model(project_id, user, p.download_link, viewer)

        response = create_redirect_response(
            request.app,
            page="view",
            project_id=project_id,
            file_name=p.file_name,
            file_size=p.file_size,
        )
        await ensure_authentication(user, request, response)

    except MatchNotFoundError as err:
        raise create_redirect_response(
            request.app,
            page="error",
            message=f"Sorry, we cannot render this file: {err.reason}",
        )
    except (ValidationError, web.HTTPServerError):
        log.exception("Validation failure while processing view request: %s", p)
        raise create_redirect_response(
            request.app,
            page="error",
            message="Ups something went wrong while processing your request",
        )
    except web.HTTPClientError as err:
        raise create_redirect_response(
            request.app, page="error", message=err.reason, status_code=err.status_code
        )

    return response
