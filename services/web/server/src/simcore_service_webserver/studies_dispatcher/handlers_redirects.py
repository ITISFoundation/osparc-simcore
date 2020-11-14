""" Handles request to the viewers redirection entrypoints

"""

import logging
from typing import Optional

from aiohttp import web
from pydantic import BaseModel, HttpUrl, ValidationError
from yarl import URL

from ..statics import INDEX_RESOURCE_NAME
from ._core import MatchNotFoundError, find_compatible_viewer, ViewerInfo, compose_uuid_from
from ._projects import create_viewer_project_model
from ._users import acquire_user, ensure_authentication, UserInfo

log = logging.getLogger(__name__)


class ValidationMixin:
    @classmethod
    def create_from(cls, request: web.Request):
        try:
            obj = cls(**request.query.keys())
        except ValidationError as err:
            raise web.HTTPBadRequest(content_type="application/json", body=err.json())
        else:
            return obj


# TODO: create dinamically with pydantic class
class RequestParams(BaseModel, ValidationMixin):
    file_name: Optional[str] = None
    file_size: int
    file_type: str
    download_link: HttpUrl


def create_redirect_response(app: web.Application, page: str, **parameters):
    page = page.strip(" /")
    # TODO: test that fragment queries are understood by front-end
    # TODO: front end should create an error page and a view page
    assert page in ("view", "error") # nosec

    in_fragment = str(URL.build(path=f"/{page}").with_query(**parameters))
    redirect_url = app.router[INDEX_RESOURCE_NAME].url_for().with_fragment(in_fragment)
    return web.HTTPFound(location=redirect_url)


# HANDLERS --------------------------------


async def get_redirection_to_viewer(request: web.Request):
    p = RequestParams.create_from(request)  # validated parameters

    try:
        viewer: ViewerInfo = find_compatible_viewer(p.file_size, p.file_type)

        # retrieve user or create a temporary guest
        user: UserInfo = await acquire_user(request)

        # Generate one project per user + download_link + viewer
        project_id = compose_uuid_from(user.email, viewer.footprint, p.download_link)


        # already exists?
            # yes. user has access??
                # yes
                    # redirect
                # no
                    # assign access
                    # save
                    # redirect
            # no.
                # create new
                # save
                # redirect



        # create project with file-picker (download_link) and viewer
        project = create_viewer_project_model(
            project_id, user, p.download_link, viewer
        )


        response = create_redirect_response(
            request.app,
            page="view",
            project_id=project_id,
            file_name=p.file_name,
            file_size=p.file_size,
        )
        await ensure_authentication(user, request, response)

    except ValidationError as err:
        log.exception(err)
        raise create_redirect_response(
            request.app,
            page="error",
            message="Ups something went wrong while processing your request",
        )

    except MatchNotFoundError as err:
        raise create_redirect_response(
            request.app,
            page="error",
            message="Sorry, we cannot render this file: {err.reason}",
        )

    return response
