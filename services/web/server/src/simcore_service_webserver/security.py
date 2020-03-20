""" Security subsystem.

    - Responsible of authentication and authorization


    See login/decorators.py
    Based on https://aiohttp-security.readthedocs.io/en/latest/
"""
# pylint: disable=assignment-from-no-return
import logging

import aiohttp_security
from aiohttp import web
from aiohttp_security.session_identity import SessionIdentityPolicy

from servicelib.application_setup import ModuleCategory, app_module_setup

from .security_access_model import RoleBasedAccessModel
from .security_authorization import AuthorizationPolicy
from .security_roles import ROLES_PERMISSIONS

log = logging.getLogger(__file__)


@app_module_setup(__name__, ModuleCategory.SYSTEM, logger=log)
def setup(app: web.Application):
    # Once user is identified, an identity string is created for that user
    identity_policy = SessionIdentityPolicy()

    # TODO: limitations is that it cannot contain checks need to be added here
    access_model = RoleBasedAccessModel.from_rawdata(ROLES_PERMISSIONS)

    # TODO: create basic/bearer authentication policy based on tokens instead of cookies!!
    # when you do that, also update the openapi to reflect that
    authorization_policy = AuthorizationPolicy(app, access_model)
    aiohttp_security.setup(app, identity_policy, authorization_policy)


setup_security = setup

__all__ = "setup_security"
