""" handles access to studies

    Handles a request to share a given sharable study via '/study/{id}'

    - defines '/study/{id}' routes (this route does NOT belong to restAPI)
    - access to projects management subsystem
    - access to statics
    - access to security
    - access to login

FIXME: reduce modules coupling!
TODO: THIS IS A PROTOTYPE!!!

"""
import logging
from typing import Dict

from aiohttp import web

from .security import is_anonymous, remember
from .statics import index as app_index

log = logging.getLogger(__name__)


# TODO: from .projects import get_template_project
async def get_template_project(app: web.Application, project_uuid: str):
    from .projects_fakes import Fake
    from .projects_models import ProjectDB
    from servicelib.application_keys import APP_DB_ENGINE_KEY

    # TODO: user search queries in DB instead
    projects_list  = [prj.data for prj in Fake.projects.values() if prj.template]
    projects_list += await ProjectDB.load_template_projects(db_engine=app[APP_DB_ENGINE_KEY])

    for prj in projects_list:
        if prj.uuid == project_uuid:
            return prj
    return None

# TODO: from .users import create_temporary_user
async def create_temporary_user(request: web.Request):
    """
        TODO: user should have an expiration date and limited persmissions!
    """
    from .login.cfg import get_storage
    from .login.handlers import ACTIVE, ANONYMOUS
    from .login.utils import get_client_ip
    from .security import encrypt_password
    from .utils import generate_passphrase, generate_password

    db = get_storage(request.app)

    # TODO: avatar is an icon of the hero!
    username = generate_passphrase(number_of_words=2).replace(" ", "_")
    email = username + "@anonymous-osparc.io"
    password = generate_password()

    user = await db.create_user({
        'name': username,
        'email': email,
        'password_hash': encrypt_password(password),
        'status': ACTIVE,
        'role':  ANONYMOUS,
        'created_ip': get_client_ip(request),
    })

    return user

# TODO: from .users import get_user?
async def get_authorized_user(request: web.Request) -> Dict:
    from .login.cfg import get_storage
    from .security import authorized_userid

    db = get_storage(request.app)
    userid = await authorized_userid(request)
    user = await db.get_user({'id': userid})
    return user

# TODO: from .projects import ...?
async def ensure_study_in_account(request: web.Request, project: Dict, user_id: str):
    """ Ensures there is a copy of a given project in user's account
    """
    from servicelib.application_keys import APP_DB_ENGINE_KEY
    from .projects.projects_models import ProjectDB as db
    from .projects.projects_models import ProjectType
    from .projects.projects_exceptions import ProjectNotFoundError
    from copy import deepcopy

    db_engine = request.app[APP_DB_ENGINE_KEY]

    try:
        await db.get_user_project(user_id, project["uuid"], db_engine)
    except ProjectNotFoundError:
        copied_project = deepcopy(project)
        copied_project["type"] = ProjectType.STANDARD
        await db.add_project(copied_project, user_id, db_engine)


# -----------------------------------------------

async def access_study(request: web.Request) -> web.Response:
    """
        Handles requests to access a study in a given user's account

        - study must be a template
        - if user is not registered, it creates a temporary account (has an expiration date)
        -
    """
    study_id = request.match_info["id"]
    log.debug("Requested access to study '%s' ...", study_id)

    # FIXME: if identified user, then he can access not only to template but also his own projects!

    user = None
    # only template projects are currently sharable
    project = await get_template_project(request.app, study_id)
    if project is None:
        raise web.HTTPNotFound(reason="Could not find sharable study '%s'" % study_id)

    is_anonymous_user = await is_anonymous(request)
    if is_anonymous_user:
        log.debug("Creating temporary user ...")
        user = await create_temporary_user(request)
    else:
        user = await get_authorized_user(request)

    log.info("Ensuring study %s in account owned by %s", project['name'], user["email"])
    user_id = user["id"]
    await ensure_study_in_account(request, project, user_id)

    response = await app_index(request)
    if is_anonymous_user:
        log.info("Auto login for anonymous users")
        identity = user['email']
        await remember(request, response, identity)

    return response




def setup(app: web.Application):
    """

    :param app: [description]
    :type app: web.Application
    """

    app.router.add_routes([
        web.get(r"/study/{id:\d+}", access_study, name="study"),
    ])


# alias
setup_studies = setup

__all__ = (
    'setup_studies'
)
