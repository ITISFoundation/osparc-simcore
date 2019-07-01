""" handles access to studies

    Handles a request to share a given sharable study via '/study/{id}'

    - defines '/study/{id}' routes (this route does NOT belong to restAPI)
    - access to projects management subsystem
    - access to statics
    - access to security
    - access to login

FIXME: reduce modules coupling! See all TODO: .``from ...`` comments
TODO: THIS IS A PROTOTYPE!!!

"""
import json
import logging
import uuid
from typing import Dict

from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY

from .resources import resources
from .security_api import is_anonymous, remember
from .statics import INDEX_RESOURCE_NAME

log = logging.getLogger(__name__)

BASE_UUID = uuid.UUID("71e0eb5e-0797-4469-89ba-00a0df4d338a")


def load_isan_template_uuids():
    with resources.stream('data/fake-template-projects.isan.json') as fp:
        data = json.load(fp)
    return [prj['uuid'] for prj in data]

SHARABLE_TEMPLATE_STUDY_IDS = load_isan_template_uuids()

# TODO: from .projects import get_template_project
async def get_template_project(app: web.Application, project_uuid: str):
    # TODO: remove projects_ prefix from name
    from .projects.projects_db import APP_PROJECT_DBAPI

    db = app[APP_PROJECT_DBAPI]

    # TODO: user search queries in DB instead
    # BUG: ensure items in project_list have unique UUIDs
    projects_list = await db.load_template_projects()

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

# Creation of projects from templates ---
def compose_uuid(template_uuid, user_id) -> str:
    """ Creates a new uuid composing a project's and user ids such that
        any template pre-assigned to a user

        Enforces a constraint: a user CANNOT have multiple copies of the same template
        TODO: cache results
    """
    new_uuid = str( uuid.uuid5(BASE_UUID, str(template_uuid) + str(user_id)) )
    return new_uuid


# TODO: from .projects import ...?
async def copy_study_to_account(request: web.Request, template_project: Dict, user: Dict):
    """
        Creates a copy of the study to a given project in user's account

        Contrains of this method:
            - Avoids multiple copies of the same template on each account
    """

    from .projects.projects_db import APP_PROJECT_DBAPI
    from .projects.projects_exceptions import ProjectNotFoundError
    from .projects.projects_utils import clone_project_data

    # FIXME: ONLY projects should have access to db since it avoids access layer
    # TODO: move to project_api and add access layer
    db = request.config_dict[APP_PROJECT_DBAPI]

    # assign id to copy
    project_uuid = compose_uuid(template_project["uuid"], user["id"])

    try:
        # Avoids multiple copies of the same template on each account
        await db.get_user_project(user["id"], project_uuid)

    except ProjectNotFoundError:
        # new project from template
        project = clone_project_data(template_project)

        project["uuid"] = project_uuid
        await db.add_project(project, user["id"], force_project_uuid=True)

    return project_uuid


# -----------------------------------------------

async def access_study(request: web.Request) -> web.Response:
    """
        Handles requests to access a study in a given user's account

        - study must be a template
        - if user is not registered, it creates a temporary account (has an expiration date)
        -
    """
    study_id = request.match_info["id"]

    log.debug("Requested a copy of study '%s' ...", study_id)

    # FIXME: if identified user, then he can access not only to template but also his own projects!
    if study_id not in SHARABLE_TEMPLATE_STUDY_IDS:
        raise web.HTTPNotFound(reason="This study was not shared [{}]".format(study_id))

    # TODO: should copy **any** type of project is sharable -> get_sharable_project
    template_project = await get_template_project(request.app, study_id)
    if not template_project:
        raise web.HTTPNotFound(reason="Invalid study [{}]".format(study_id))

    user = None
    is_anonymous_user = await is_anonymous(request)
    if is_anonymous_user:
        log.debug("Creating temporary user ...")
        user = await create_temporary_user(request)
    else:
        user = await get_authorized_user(request)

    if not user:
        raise RuntimeError("Unable to start user session")

    msg_tail = "study {} to {} account ...".format(template_project.get('name'), user.get("email"))
    log.debug("Copying %s ...", msg_tail)

    copied_project_id = await copy_study_to_account(request, template_project, user)

    log.debug("Copied %s as %s", msg_tail, copied_project_id)


    try:
        loc = request.app.router[INDEX_RESOURCE_NAME].url_for().with_fragment("/study/{}".format(copied_project_id))
    except KeyError:
        raise RuntimeError("Unable to serve front-end. Study has been anyway copied over to user.")

    response = web.HTTPFound(location=loc)
    if is_anonymous_user:
        log.debug("Auto login for anonymous user %s", user["name"])
        identity = user['email']
        await remember(request, response, identity)

    raise response


def setup(app: web.Application):

    cfg = app[APP_CONFIG_KEY]["main"]
    if not cfg["studies_access_enabled"]:
        log.warning("'%s' setup explicitly disabled in config", __name__)
        return False

    # TODO: make sure that these routes are filtered properly in active middlewares
    app.router.add_routes([
        web.get(r"/study/{id}", access_study, name="study"),
    ])

    return True


# alias
setup_studies_access = setup

__all__ = (
    'setup_studies_access'
)
