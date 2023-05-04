from typing import Any, Callable, Coroutine

from aiohttp import web
from models_library.projects import ProjectID
from pydantic import BaseModel, HttpUrl

_PROJECT_PERMALINK = f"{__name__}"


class ProjectPermalink(BaseModel):
    url: HttpUrl
    is_public: bool


_CreateLinkCallable = Callable[
    [web.Application, ProjectID], Coroutine[Any, Any, ProjectPermalink]
]


def register_factory(app: web.Application, factory_coro: _CreateLinkCallable):
    app[_PROJECT_PERMALINK] = factory_coro


def _get_factory(app: web.Application) -> _CreateLinkCallable | None:
    return app.get(_PROJECT_PERMALINK)


async def create_permalink(
    app: web.Application, project_id: ProjectID
) -> ProjectPermalink | None:
    if factory := _get_factory(app):
        # TODO: timeout
        # TODO: raised exceptions?
        permalink_info: ProjectPermalink = await factory(app, project_id)
        return permalink_info
    return None
