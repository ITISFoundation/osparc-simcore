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
import json
import logging
import uuid
from typing import Dict

from aiohttp import web

from .resources import resources
from .security import is_anonymous, remember
from .statics import index as app_index

log = logging.getLogger(__name__)

BASE_UUID = uuid.UUID("71e0eb5e-0797-4469-89ba-00a0df4d338a")


def load_isan_template_uuids():
    with resources.stream('data/fake-template-projects.isan.json') as fp:
        data = json.load(fp)
    return [prj['uuid'] for prj in data]

ALLOWED_TEMPLATE_IDS = load_isan_template_uuids()


# TODO: from .projects import get_template_project
async def get_template_project(app: web.Application, project_uuid: str):
    # TODO: remove projects_ prefix from name
    from servicelib.application_keys import APP_DB_ENGINE_KEY

    from .projects.projects_models import ProjectDB
    from .projects.projects_fakes import Fake


    # TODO: user search queries in DB instead
    # BUG: ensure items in project_list have unique UUIDs
    projects_list = [prj.data for prj in Fake.projects.values() if prj.template]
    projects_list += await ProjectDB.load_template_projects(db_engine=app[APP_DB_ENGINE_KEY])

    for prj in projects_list:
        if prj.get('uuid') == project_uuid:
            return prj
    return None

# TODO: from .users import create_temporary_user
async def create_temporary_user(request: web.Request):
    """
        TODO: user should have an expiration date and limited persmissions!
    """
    from .login.cfg import get_storage
    from .login.handlers import ACTIVE, ANONYMOUS
    from .login.utils import get_client_ip, get_random_string
    from .security import encrypt_password
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
        'role':  ANONYMOUS, # TODO: THIS has to be a temporary user!
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
async def copy_study_to_account(request: web.Request, project: Dict, user_id: str):
    """
        Creates a copy of the study to a given project in user's account

        Contrains of this method:
            - Avoids multiple copies of the same template on each account
    """
    from servicelib.application_keys import APP_DB_ENGINE_KEY
    from .projects.projects_models import ProjectDB as db
    from .projects.projects_models import ProjectType
    from .projects.projects_exceptions import ProjectNotFoundError
    from copy import deepcopy

    db_engine = request.app[APP_DB_ENGINE_KEY]
    new_uuid = str( uuid.uuid5(BASE_UUID, project["uuid"] + str(user_id)) )

    try:
        # Avoids multiple copies of the same template on each account
        await db.get_user_project(user_id, new_uuid, db_engine)

    except ProjectNotFoundError:

        copied_project = deepcopy(project)
        copied_project["type"] = ProjectType.STANDARD
        copied_project["uuid"] = new_uuid

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
    if study_id not in ALLOWED_TEMPLATE_IDS:
        raise web.HTTPNotFound(reason="Could not find sharable study '%s'" % study_id)

    project = await get_template_project(request.app, study_id)
    assert (project is not None), "Failed to load project"

    is_anonymous_user = await is_anonymous(request)
    if is_anonymous_user:
        log.debug("Creating temporary user ...")
        user = await create_temporary_user(request)
    else:
        user = await get_authorized_user(request)

    log.info("Ensuring study %s in account owned by %s", project['name'], user["email"])
    user_id = user["id"]
    await copy_study_to_account(request, project, user_id)

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

    # TODO: make sure that these routes are filtered properly in active middlewares
    app.router.add_routes([
        web.get(r"/study/{id}", access_study, name="study"),
    ])


# alias
setup_studies_access = setup

__all__ = (
    'setup_studies_access'
)
