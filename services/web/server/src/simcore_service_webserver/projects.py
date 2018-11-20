""" projects management subsystem


"""
import logging

from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.rest_routing import iter_path_operations, map_handlers_with_operations, get_handlers_from_namespace

from . import projects_handlers
from .rest_config import APP_OPENAPI_SPECS_KEY
from .projects_fakes import Fake

CONFIG_SECTION_NAME = "projects"


logger = logging.getLogger(__name__)

def setup(app: web.Application, *, debug=False):
    logger.debug("Setting up %s %s...", __name__, "[debug]" if debug else "")

    assert CONFIG_SECTION_NAME not in app[APP_CONFIG_KEY], "Not section for the moment"

    # routes
    specs = app[APP_OPENAPI_SPECS_KEY]

    routes = map_handlers_with_operations(
            get_handlers_from_namespace(projects_handlers),
            filter(lambda o: "/projects" in o[1],  iter_path_operations(specs)),
            strict=True
    )
    app.router.add_routes(routes)

    # debug
    if debug:
        Fake.load_user_projects(1)
        Fake.load_template_projects()


# alias
setup_projects = setup

__all__ = (
    'setup_projects'
)
