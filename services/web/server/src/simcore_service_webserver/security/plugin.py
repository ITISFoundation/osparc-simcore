""" Security subsystem.

    - Responsible of authentication and authorization


    See login/decorators.py
    Based on https://aiohttp-security.readthedocs.io/en/latest/
"""
import logging

import aiohttp_security
from aiohttp import web
from aiohttp_security.session_identity import SessionIdentityPolicy
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from ..session.plugin import setup_session
from ._authz import AuthorizationPolicy
from ._authz_access_model import RoleBasedAccessModel
from ._authz_access_roles import ROLES_PERMISSIONS

_logger = logging.getLogger(__name__)


@app_module_setup(
    __name__, ModuleCategory.SYSTEM, settings_name="WEBSERVER_SECURITY", logger=_logger
)
def setup_security(app: web.Application):

    setup_session(app)

    # Identity Policy: uses sessions to identify (SEE how sessions are setup in session/plugin.py)
    identity_policy = SessionIdentityPolicy()

    # Authorization Policy: role-based access model
    role_based_access_model = RoleBasedAccessModel.from_rawdata(ROLES_PERMISSIONS)
    authorization_policy = AuthorizationPolicy(
        app, access_model=role_based_access_model
    )
    aiohttp_security.setup(app, identity_policy, authorization_policy)
