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

from ._access_model import RoleBasedAccessModel
from ._access_roles import ROLES_PERMISSIONS
from ._authorization import AuthorizationPolicy

_logger = logging.getLogger(__name__)


@app_module_setup(
    __name__, ModuleCategory.SYSTEM, settings_name="WEBSERVER_SECURITY", logger=_logger
)
def setup_security(app: web.Application):
    # Once user is identified, an identity string is created for that user
    identity_policy = SessionIdentityPolicy()

    # Authorization
    role_based_access_model = RoleBasedAccessModel.from_rawdata(ROLES_PERMISSIONS)
    authorization_policy = AuthorizationPolicy(
        app, access_model=role_based_access_model
    )
    aiohttp_security.setup(app, identity_policy, authorization_policy)
