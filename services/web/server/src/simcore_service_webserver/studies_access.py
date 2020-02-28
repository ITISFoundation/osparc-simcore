""" handles access to *public* studies

    Handles a request to share a given sharable study via '/study/{id}'

    - defines '/study/{id}' routes (this route does NOT belong to restAPI)
    - access to projects management subsystem
    - access to statics
    - access to security
    - access to login

FIXME: Refactor to reduce modules coupling! See all TODO: .``from ...`` comments
"""
import logging
import uuid
from functools import lru_cache
from typing import Dict

from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.application_setup import ModuleCategory, app_module_setup

from .login.decorators import login_required
from .security_api import is_anonymous, remember
from .statics import INDEX_RESOURCE_NAME

log = logging.getLogger(__name__)

BASE_UUID = uuid.UUID("71e0eb5e-0797-4469-89ba-00a0df4d338a")

@lru_cache()
def compose_uuid(template_uuid, user_id, query="") -> str:
    """ Creates a new uuid composing a project's and user ids such that
        any template pre-assigned to a user

        Enforces a constraint: a user CANNOT have multiple copies of the same template
    """
    new_uuid = str( uuid.uuid5(BASE_UUID, str(template_uuid) + str(user_id) + str(query)) )
    return new_uuid


# TODO: from .projects import get_public_project
async def get_public_project(app: web.Application, project_uuid: str):
    """
        Returns project if project_uuid is a template and is marked as published, otherwise None
    """
    from .projects.projects_db import APP_PROJECT_DBAPI

    db = app[APP_PROJECT_DBAPI]
    prj = await db.get_template_project(project_uuid, only_published=True)
    return prj

# TODO: from .users import create_temporary_user
async def create_temporary_user(request: web.Request):
    """
        TODO: user should have an expiration date and limited persmissions!
    """
    from .login.cfg import get_storage
    from .login.handlers import ACTIVE, GUEST
    from .login.utils import get_client_ip, get_random_string
    from .security_api import encrypt_password
    # from .utils import generate_passphrase
    # from .utils import generate_password

    db = get_storage(request.app)

    # TODO: avatar is an icon of the hero!
    # FIXME: # username = generate_passphrase(number_of_words=2).replace(" ", "_").replace("'", "")
    username = get_random_string(min_len=5)
    email = username + "@guest-at-osparc.io"
    # TODO: temporarily while developing, a fixed password
    password = "guest" #generate_password()

    user = await db.create_user({
        'name': username,
        'email': email,
        'password_hash': encrypt_password(password),
        'status': ACTIVE,
        'role':  GUEST,
        'created_ip': get_client_ip(request),
    })

    return user

# TODO: from .users import get_user?
async def get_authorized_user(request: web.Request) -> Dict:
    from .login.cfg import get_storage
    from .security_api import authorized_userid

    db = get_storage(request.app)
    userid = await authorized_userid(request)
    user = await db.get_user({'id': userid})
    return user

# TODO: from .projects import ...?
async def copy_study_to_account(request: web.Request, template_project: Dict, user: Dict):
    """
        Creates a copy of the study to a given project in user's account

        - Replaces template parameters by values passed in query
        - Avoids multiple copies of the same template on each account
    """
    from .projects.projects_db import APP_PROJECT_DBAPI
    from .projects.projects_exceptions import ProjectNotFoundError
    from .projects.projects_utils import substitute_parameterized_inputs
    from .projects.projects_api import clone_project

    # FIXME: ONLY projects should have access to db since it avoids access layer
    # TODO: move to project_api and add access layer
    db = request.config_dict[APP_PROJECT_DBAPI]
    template_parameters = dict(request.query)

    # assign id to copy
    project_uuid = compose_uuid(template_project["uuid"], user["id"], str(template_parameters))

    try:
        # Avoids multiple copies of the same template on each account
        await db.get_user_project(user["id"], project_uuid)

        # FIXME: if template is parametrized and user has already a copy, then delete it and create a new one??

    except ProjectNotFoundError:
        # new project from template
        project = await clone_project(request, template_project, user["id"], forced_copy_project_id=project_uuid)

        # check project inputs and substitute template_parameters
        if template_parameters:
            log.info("Substituting parameters '%s' in template", template_parameters)
            project = substitute_parameterized_inputs(project, template_parameters) or project

        await db.add_project(project, user["id"], force_project_uuid=True)

    return project_uuid


# HANDLERS --------------------------------------------------------
async def access_study(request: web.Request) -> web.Response:
    """
        Handles requests to get and open a public study

        - public studies are templates that are marked as published in the database
        - if user is not registered, it creates a temporary guest account with limited resources and expiration
    """
    project_id = request.match_info["id"]

    template_project = await get_public_project(request.app, project_id)
    if not template_project:
        raise web.HTTPNotFound(reason=f"Requested study ({project_id}) has not been published.\
             Please contact the data curators for more information.")

    user = None
    is_anonymous_user = await is_anonymous(request)
    if is_anonymous_user:
        log.debug("Creating temporary user ...")
        user = await create_temporary_user(request)
    else:
        user = await get_authorized_user(request)

    if not user:
        raise RuntimeError("Unable to start user session")

    log.debug("Granted access to study '%d' for user %s. Copying study over ...", template_project.get('name'), user.get('email'))
    copied_project_id = await copy_study_to_account(request, template_project, user)

    log.debug("Study %s copied", copied_project_id)

    try:
        redirect_url = request.app.router[INDEX_RESOURCE_NAME].url_for().with_fragment("/study/{}".format(copied_project_id))
    except KeyError:
        log.error("Cannot redirect to website because route was not registered. Probably qx output was not ready and it was disabled (see statics.py)")
        raise RuntimeError("Unable to serve front-end. Study has been anyway copied over to user.")

    response = web.HTTPFound(location=redirect_url)
    if is_anonymous_user:
        log.debug("Auto login for anonymous user %s", user["name"])
        identity = user['email']
        await remember(request, response, identity)

    raise response


@app_module_setup(__name__, ModuleCategory.ADDON,
    logger=log)
def setup(app: web.Application):

    cfg = app[APP_CONFIG_KEY]["main"]
    # TODO: temporarily used to toggle to logged users
    study_handler = access_study
    if not cfg["studies_access_enabled"]:
        study_handler = login_required(access_study)
        log.warning("'%s' config explicitly disables anonymous users from this feature", __name__)

    # TODO: make sure that these routes are filtered properly in active middlewares
    app.router.add_routes([
        web.get(r"/study/{id}", study_handler, name="study"),
    ])

    return True

# alias
setup_studies_access = setup

__all__ = (
    'setup_studies_access'
)
