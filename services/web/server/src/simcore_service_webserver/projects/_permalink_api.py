import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any, cast

from aiohttp import web
from models_library.api_schemas_webserver.permalinks import ProjectPermalink
from models_library.projects import ProjectID

from .exceptions import PermalinkFactoryError, PermalinkNotAllowedError
from .models import ProjectDict

_PROJECT_PERMALINK = f"{__name__}"
_logger = logging.getLogger(__name__)

_CreateLinkCallable = Callable[
    [web.Request, ProjectID], Coroutine[Any, Any, ProjectPermalink]
]


def register_factory(app: web.Application, factory_coro: _CreateLinkCallable):
    if _create := app.get(_PROJECT_PERMALINK):
        msg = f"Permalink factory can only be set once: registered {_create}"
        raise PermalinkFactoryError(msg)
    app[_PROJECT_PERMALINK] = factory_coro


def _get_factory(app: web.Application) -> _CreateLinkCallable:
    if _create := app.get(_PROJECT_PERMALINK):
        return cast(_CreateLinkCallable, _create)

    msg = "Undefined permalink factory. Check plugin initialization."
    raise PermalinkFactoryError(msg)


_PERMALINK_CREATE_TIMEOUT_S = 2


async def _create_permalink(
    request: web.Request, project_id: ProjectID
) -> ProjectPermalink:
    create = _get_factory(request.app)
    assert create  # nosec

    try:
        permalink: ProjectPermalink = await asyncio.wait_for(
            create(request, project_id), timeout=_PERMALINK_CREATE_TIMEOUT_S
        )
        return permalink
    except asyncio.TimeoutError as err:
        msg = f"Permalink factory callback '{create}' timed out after {_PERMALINK_CREATE_TIMEOUT_S} secs"
        raise PermalinkFactoryError(msg) from err


async def update_or_pop_permalink_in_project(
    request: web.Request, project: ProjectDict
) -> ProjectPermalink | None:
    """Updates permalink entry in project

    Creates a permalink for this project and assigns it to project["permalink"]

    If fails, it pops it from project (so it is not set in the pydantic model. SEE ProjectGet.permalink)
    """
    try:
        permalink = await _create_permalink(request, project_id=project["uuid"])

        assert permalink  # nosec
        project["permalink"] = permalink

        return permalink

    except (PermalinkNotAllowedError, PermalinkFactoryError):
        project.pop("permalink", None)

    return None


__all__: tuple[str, ...] = ("ProjectPermalink",)
