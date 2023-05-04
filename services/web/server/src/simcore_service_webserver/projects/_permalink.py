from typing import Any, Callable, Coroutine

from aiohttp import web
from models_library.projects import ProjectID
from pydantic import BaseModel, HttpUrl

_PROJECT_PERMALINK = f"{__name__}"


class ProjectPermalink(BaseModel):
    url: HttpUrl
    is_public: bool


_CreateLinkCallable = Callable[
    [web.Request, ProjectID], Coroutine[Any, Any, ProjectPermalink]
]


def register_factory(app: web.Application, factory_coro: _CreateLinkCallable):
    # FIXME: only once!
    app[_PROJECT_PERMALINK] = factory_coro


def _get_factory(app: web.Application) -> _CreateLinkCallable | None:
    return app.get(_PROJECT_PERMALINK)


async def create_permalink(
    request: web.Request, project_id: ProjectID
) -> ProjectPermalink | None:
    if create := _get_factory(request.app):
        # TODO: timeout
        # TODO: raised exceptions?
        permalink_info: ProjectPermalink = await create(request, project_id)
        return permalink_info
    return None
